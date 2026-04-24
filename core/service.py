from __future__ import annotations

from .auth import login_and_get_cookies
from .client import BiliRewardClient, format_cookies_text, should_relogin_from_error
from .errors import BiliCookieInvalidError, BiliRewardCancelledError, BiliRewardError
from .logging_utils import EventLogger, ScopedLogger
from .models import (
    AwardInfo,
    ClaimExecutionControl,
    ClaimOptions,
    ClaimResult,
    LinkTaskItem,
    OptionalCancelCheck,
    OptionalQrCodeCallback,
    PreparedLinkTask,
)
from .storage import (
    ensure_runtime_dirs,
    get_runtime_paths,
    load_cookie_file,
    save_cookie_file,
)


class RewardService:
    def __init__(self, base_dir: str | None = None) -> None:
        self.paths = get_runtime_paths(base_dir)
        ensure_runtime_dirs(self.paths)

    def create_logger(self, log_callback=None) -> EventLogger:
        return EventLogger(self.paths.log_file, log_callback=log_callback)

    def prepare_link_task(
        self,
        link_task: LinkTaskItem,
        *,
        log_callback=None,
        qr_callback: OptionalQrCodeCallback = None,
        cancel_check: OptionalCancelCheck = None,
        log_scope: str | None = None,
    ) -> PreparedLinkTask:
        base_logger = self.create_logger(log_callback)
        logger = ScopedLogger(base_logger, log_scope) if log_scope else base_logger
        logger.log("[任务] 开始执行领取流程")
        logger.log(f"[任务] 当前任务 ID: {link_task.task_id}")
        options = ClaimOptions(task_id=link_task.task_id)
        client, award_info = self._get_client_and_award_info(
            options,
            logger=logger,
            qr_callback=qr_callback,
            cancel_check=cancel_check,
        )
        return PreparedLinkTask(
            index=link_task.index,
            task_url=link_task.task_url,
            task_id=link_task.task_id,
            options=options,
            client=client,
            award_info=award_info,
            logger=logger,
        )

    def claim_prepared_task(
        self,
        prepared_task: PreparedLinkTask,
        *,
        claim_control: ClaimExecutionControl | None = None,
        claim_stage_callback=None,
    ) -> ClaimResult:
        if claim_stage_callback is not None:
            claim_stage_callback(True)
        try:
            award_info, cdkey = prepared_task.client.claim_award(
                prepared_task.task_id,
                thread_count=prepared_task.options.thread_count,
                max_retry=prepared_task.options.max_retry,
                retry_interval=prepared_task.options.retry_interval,
                log_callback=prepared_task.logger.log,
                claim_control=claim_control,
                award_info=prepared_task.award_info,
            )
            prepared_task.logger.log(
                f"[任务] 奖励信息: act_name={award_info.act_name}, "
                f"task_name={award_info.task_name}, award_name={award_info.award_name}"
            )
            prepared_task.logger.log(f"[任务] 领取成功，cdkey={cdkey}")
            return ClaimResult(award_info=award_info, cdkey=cdkey)
        except BiliRewardCancelledError:
            prepared_task.logger.log("[任务] 已取消抢奖")
            raise
        finally:
            if claim_stage_callback is not None:
                claim_stage_callback(False)

    def run_claim(
        self,
        options: ClaimOptions,
        *,
        log_callback=None,
        qr_callback: OptionalQrCodeCallback = None,
        cancel_check: OptionalCancelCheck = None,
        claim_control: ClaimExecutionControl | None = None,
        claim_stage_callback=None,
    ) -> ClaimResult:
        prepared = self.prepare_link_task(
            LinkTaskItem(index=0, task_url="", task_id=options.task_id),
            log_callback=log_callback,
            qr_callback=qr_callback,
            cancel_check=cancel_check,
        )
        relogin_attempted = False
        while True:
            try:
                return self.claim_prepared_task(
                    prepared,
                    claim_control=claim_control,
                    claim_stage_callback=claim_stage_callback,
                )
            except BiliCookieInvalidError as exc:
                if relogin_attempted:
                    raise BiliRewardError(f"[Cookie] 重新登录后仍然失效: {exc}") from exc
                relogin_attempted = True
                prepared.logger.log("[Cookie] 领取时检测到登录失效，正在重新扫码登录")
                cookies = login_and_get_cookies(
                    log_callback=prepared.logger.log,
                    qr_callback=qr_callback,
                    cancel_check=cancel_check,
                )
                save_cookie_file(self.paths.cookie_file, cookies)
                prepared.logger.log(f"[Cookie] 已保存到本地: {self.paths.cookie_file}")
                prepared = self.prepare_link_task(
                    LinkTaskItem(index=0, task_url="", task_id=options.task_id),
                    log_callback=log_callback,
                    qr_callback=qr_callback,
                    cancel_check=cancel_check,
                )

    def _get_client_and_award_info(
        self,
        options: ClaimOptions,
        *,
        logger: EventLogger,
        qr_callback: OptionalQrCodeCallback = None,
        cancel_check: OptionalCancelCheck = None,
    ) -> tuple[BiliRewardClient, AwardInfo]:
        local_cookies = load_cookie_file(self.paths.cookie_file)
        if local_cookies:
            logger.log("[Cookie] 已加载本地 Cookie")
            try:
                local_cookie_text = format_cookies_text(local_cookies)
                client = BiliRewardClient(local_cookie_text, timeout=options.timeout)
                client.ensure_logged_in()
                award_info = client.get_award_info(options.task_id, log_callback=logger.log)
                return client, award_info
            except BiliRewardError as exc:
                if should_relogin_from_error(exc):
                    logger.log("[Cookie] 本地 Cookie 可能已失效，正在重新扫码登录")
                else:
                    raise
        else:
            logger.log(f"[Cookie] 本地 Cookie 不存在或不可用: {self.paths.cookie_file}")

        fresh_cookies = login_and_get_cookies(
            log_callback=logger.log,
            qr_callback=qr_callback,
            cancel_check=cancel_check,
        )
        save_cookie_file(self.paths.cookie_file, fresh_cookies)
        logger.log(f"[Cookie] 已保存到本地: {self.paths.cookie_file}")
        fresh_cookie_text = format_cookies_text(fresh_cookies)
        client = BiliRewardClient(fresh_cookie_text, timeout=options.timeout)
        award_info = client.get_award_info(options.task_id, log_callback=logger.log)
        return client, award_info

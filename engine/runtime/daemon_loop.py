"""守护进程主循环 — Phase 5 从 AutopilotDaemon 收拢到 engine/runtime

重构: 异步并行处理多本小说，支持并发上限控制。
"""
from __future__ import annotations

import asyncio
import logging
import time
from typing import Any, Protocol, runtime_checkable

logger = logging.getLogger(__name__)


@runtime_checkable
class DaemonLoopHost(Protocol):
    """守护进程主循环所需的最小 host 接口"""

    poll_interval: int
    max_concurrent_novels: int
    circuit_breaker: Any

    def _write_daemon_heartbeat(self) -> None: ...
    def _get_active_novels(self) -> list: ...
    def _cleanup_stale_stop_signals(self, active_novels: list) -> None: ...
    async def _process_novel(self, novel: Any) -> None: ...


async def _async_main_loop(host: DaemonLoopHost, *, loop_count_start: int = 0) -> None:
    """异步主循环 — 并行处理多本小说，带并发上限。"""
    loop_count = loop_count_start
    max_concurrent = getattr(host, "max_concurrent_novels", 3)
    semaphore = asyncio.Semaphore(max_concurrent)

    while True:
        loop_count += 1
        loop_start = time.time()

        host._write_daemon_heartbeat()

        if host.circuit_breaker and host.circuit_breaker.is_open():
            wait = host.circuit_breaker.wait_seconds()
            logger.warning("熔断器打开，暂停 %.0fs", wait)
            await asyncio.sleep(min(wait, host.poll_interval))
            continue

        try:
            try:
                from application.engine.services.streaming_bus import streaming_bus

                streaming_bus.consume_stop_signals()
            except Exception:
                pass

            active_novels = host._get_active_novels()

            if active_novels:
                host._cleanup_stale_stop_signals(active_novels)

            if loop_count % 10 == 1:
                logger.info(
                    "Loop #%s: 发现 %s 本活跃小说 (并发上限: %s)",
                    loop_count, len(active_novels), max_concurrent,
                )

            if active_novels:
                async def _process_with_limit(novel: Any, idx: int = 0) -> None:
                    novel_id = getattr(getattr(novel, "novel_id", None), "value", novel)
                    async with semaphore:
                        novel_start = time.time()
                        logger.debug("   [%s] 开始处理", novel_id)
                        await host._process_novel(novel)
                        novel_elapsed = time.time() - novel_start
                        logger.debug(
                            "   [%s] 处理耗时: %.2fs",
                            novel_id, novel_elapsed,
                        )

                # 并行处理所有活跃小说，单个失败不影响其他
                results = await asyncio.gather(
                    *[_process_with_limit(n, i) for i, n in enumerate(active_novels)],
                    return_exceptions=True,
                )
                for i, result in enumerate(results):
                    if isinstance(result, Exception):
                        novel_id = getattr(
                            getattr(active_novels[i], "novel_id", None), "value",
                            active_novels[i],
                        )
                        logger.error(
                            "   [%s] 并行处理异常: %s", novel_id, result,
                            exc_info=result,
                        )

        except Exception as e:
            logger.error("Daemon 顶层异常: %s", e, exc_info=True)

        loop_elapsed = time.time() - loop_start
        if loop_elapsed > host.poll_interval * 2:
            logger.warning("Loop #%s 耗时过长: %.2fs", loop_count, loop_elapsed)

        await asyncio.sleep(host.poll_interval)


def run_daemon_loop(host: DaemonLoopHost, *, banner: str | None = None) -> None:
    """守护进程主循环 — 并行处理多本小说

    AutopilotDaemon、StoryPipelineRunner、EngineDaemon 共用此循环。
    所有活跃小说通过 asyncio.gather 并行处理，受 max_concurrent_novels 信号量限制。
    """
    if banner:
        logger.info("=" * 80)
        logger.info(banner)
        logger.info("=" * 80)

    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

    try:
        loop.run_until_complete(_async_main_loop(host))
    finally:
        loop.close()

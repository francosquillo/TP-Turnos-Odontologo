"""Task 2.5 GREEN: worker stub C-01 (jobs reales en C-06). Solo heartbeat."""
import asyncio
import logging

logger = logging.getLogger("worker.stub")


async def heartbeat(interval_s: float = 30.0) -> None:
    logger.info("worker stub C-01 heartbeat cada %ss", interval_s)
    while True:
        logger.info("worker stub C-01 alive")
        await asyncio.sleep(interval_s)


async def main() -> None:
    logger.info("worker stub C-01 iniciado (sin jobs hasta C-06)")
    await heartbeat()


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    asyncio.run(main())

from datetime import timedelta

from temporalio import workflow

with workflow.unsafe.imports_passed_through():
    from app.temporal.activities import process_content


@workflow.defn
class ContentProcessingWorkflow:
    @workflow.run
    async def run(self, content_id: int) -> str:
        result = await workflow.execute_activity(
            process_content,
            content_id,
            start_to_close_timeout=timedelta(minutes=5),
        )
        return result

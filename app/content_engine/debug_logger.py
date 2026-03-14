"""
Content Engine — Pipeline Debug Logger

Configurable logging for pipeline stage inputs/outputs.

Usage:
    Set env var: CONTENT_ENGINE_DEBUG=stages    (log stage summaries)
    Set env var: CONTENT_ENGINE_DEBUG=prompts   (log full prompts + responses)
    Set env var: CONTENT_ENGINE_DEBUG=off       (default — normal logging only)

    Or pass debug_level to pipeline.generate():
        pipeline.generate(..., debug_level='prompts')
"""

import os
import json
import logging
from typing import Dict, List, Any, Optional
from datetime import datetime

logger = logging.getLogger('content_engine.debug')

# Debug levels
DEBUG_OFF = 'off'           # Normal logging only
DEBUG_STAGES = 'stages'     # Log stage summaries (context keys, topic count, post titles)
DEBUG_PROMPTS = 'prompts'   # Log full prompts and AI responses

VALID_LEVELS = {DEBUG_OFF, DEBUG_STAGES, DEBUG_PROMPTS}


def get_debug_level(override: str = None) -> str:
    """Get debug level from override, env var, or default."""
    level = override or os.getenv('CONTENT_ENGINE_DEBUG', DEBUG_OFF)
    level = level.lower().strip()
    if level not in VALID_LEVELS:
        logger.warning(f"Invalid debug level '{level}', using '{DEBUG_OFF}'")
        return DEBUG_OFF
    return level


class PipelineDebugger:
    """
    Logs pipeline stage inputs and outputs at configurable detail levels.

    'stages' level: key counts, summaries, timing
    'prompts' level: full prompt text and AI response text
    """

    def __init__(self, debug_level: str = None):
        self.level = get_debug_level(debug_level)
        self._stage_times = {}
        self.enabled = self.level != DEBUG_OFF

    def log_stage_start(self, stage: str):
        """Mark the start of a stage for timing."""
        self._stage_times[stage] = datetime.utcnow()
        if self.enabled:
            logger.info(f"{'='*60}")
            logger.info(f"STAGE: {stage}")
            logger.info(f"{'='*60}")

    def log_stage_end(self, stage: str, summary: str = ''):
        """Mark the end of a stage with optional summary."""
        elapsed = ''
        if stage in self._stage_times:
            delta = datetime.utcnow() - self._stage_times[stage]
            elapsed = f" ({delta.total_seconds():.1f}s)"
        if self.enabled:
            logger.info(f"STAGE {stage} COMPLETE{elapsed}: {summary}")

    # ── Stage 0: Context ──

    def log_context(self, ctx: Dict):
        """Log assembled context."""
        if not self.enabled:
            return

        logger.info(f"[Context] vertical={ctx.get('vertical')}, "
                     f"platform={ctx.get('platform')}, "
                     f"posts_needed={ctx.get('posts_needed')}")
        logger.info(f"[Context] opportunities={len(ctx.get('opportunity_summaries', []))}, "
                     f"recent_posts={len(ctx.get('recent_posts', []))}")
        logger.info(f"[Context] trending: "
                     f"pulse={len(ctx.get('trending_data', {}).get('social_pulse', []))}, "
                     f"topics={len(ctx.get('trending_data', {}).get('topics', []))}, "
                     f"news={len(ctx.get('trending_data', {}).get('news', []))}, "
                     f"hashtags={len(ctx.get('trending_data', {}).get('hashtags', []))}")
        logger.info(f"[Context] curated_topics={len(ctx.get('curated_topics', []))}")
        logger.info(f"[Context] seasonal_triggers={len(ctx.get('resolved_config', {}).get('seasonal_triggers', []))}")

        if self.level == DEBUG_PROMPTS:
            logger.info(f"[Context] voice_brief:\n{ctx.get('voice_brief', '')}")
            logger.info(f"[Context] business_summary:\n{ctx.get('business_summary', '')}")

    # ── Stage 1: Strategist ──

    def log_strategist_prompt(self, prompt: str):
        """Log the Stage 1 prompt."""
        if self.level == DEBUG_PROMPTS:
            logger.info(f"[Stage1] PROMPT ({len(prompt)} chars):\n{prompt}")
        elif self.level == DEBUG_STAGES:
            logger.info(f"[Stage1] Prompt length: {len(prompt)} chars")

    def log_strategist_response(self, response: str, topics: List[Dict]):
        """Log the Stage 1 AI response and parsed topics."""
        if self.level == DEBUG_PROMPTS:
            logger.info(f"[Stage1] RAW RESPONSE ({len(response)} chars):\n{response}")

        if self.enabled:
            logger.info(f"[Stage1] Parsed {len(topics)} topics:")
            for i, t in enumerate(topics, 1):
                logger.info(f"  {i}. [{t.get('content_type')}] {t.get('theme_title')} "
                             f"→ emotion={t.get('target_emotion')}, "
                             f"product={t.get('product_focus')}, "
                             f"source={t.get('source')}")

    # ── Stage 2: Writer ──

    def log_writer_prompt(self, post_number: int, content_type: str, prompt: str):
        """Log a Stage 2 writer prompt."""
        if self.level == DEBUG_PROMPTS:
            logger.info(f"[Stage2] POST {post_number} ({content_type}) "
                         f"PROMPT ({len(prompt)} chars):\n{prompt}")
        elif self.level == DEBUG_STAGES:
            logger.info(f"[Stage2] POST {post_number} ({content_type}) "
                         f"prompt={len(prompt)} chars")

    def log_writer_response(self, post_number: int, response: str, post: Dict):
        """Log a Stage 2 writer response."""
        if self.level == DEBUG_PROMPTS:
            logger.info(f"[Stage2] POST {post_number} RAW RESPONSE ({len(response)} chars):\n{response}")

        if self.enabled:
            content = post.get('content', '')
            word_count = len(content.split())
            logger.info(f"[Stage2] POST {post_number} written: "
                         f"title=\"{post.get('title', '')}\", "
                         f"words={word_count}, "
                         f"hashtags={post.get('hashtags', [])}")

    def log_writer_context(self, post_number: int, type_brief_source: str,
                            style_ref_count: int, hashtag_count: int):
        """Log what reference material the writer received."""
        if self.enabled:
            logger.info(f"[Stage2] POST {post_number} context: "
                         f"type_brief={type_brief_source}, "
                         f"style_refs={style_ref_count}, "
                         f"trending_hashtags={hashtag_count}")

    # ── Stage 2 Batch ──

    def log_batch_prompt(self, post_count: int, prompt: str):
        """Log the batch writer prompt."""
        if self.level == DEBUG_PROMPTS:
            logger.info(f"[Stage2-Batch] {post_count} posts, "
                         f"PROMPT ({len(prompt)} chars):\n{prompt}")
        elif self.level == DEBUG_STAGES:
            logger.info(f"[Stage2-Batch] {post_count} posts, "
                         f"prompt={len(prompt)} chars")

    def log_batch_response(self, response: str, posts: List[Dict]):
        """Log the batch writer response."""
        if self.level == DEBUG_PROMPTS:
            logger.info(f"[Stage2-Batch] RAW RESPONSE ({len(response)} chars):\n{response}")

        if self.enabled:
            for i, p in enumerate(posts, 1):
                word_count = len(p.get('content', '').split())
                logger.info(f"[Stage2-Batch] POST {i}: "
                             f"title=\"{p.get('title', '')}\", "
                             f"words={word_count}")

    # ── Stage 3: Validator ──

    def log_validator(self, posts_in: int, posts_out: int, swaps: int = 0):
        """Log validator results."""
        if self.enabled:
            logger.info(f"[Stage3] Input: {posts_in} posts, "
                         f"Output: {posts_out} posts, "
                         f"Swaps/drops: {posts_in - posts_out}")

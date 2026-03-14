"""
Content Engine — Pipeline

3-Stage pipeline for social media content calendar generation:
    Stage 0: Assemble context (code)
    Stage 1: Strategist — pick topics, assign content types (1 AI call)
    Stage 2: Writer — write posts one at a time (N AI calls)
    Stage 3: Validator — enforce rules, order calendar (code)
"""

from typing import Dict, List, Any, Optional
from datetime import datetime, timedelta
import json
import logging
import os

from .config_resolver import ConfigResolver, CONTENT_TYPES, REQUIRES_REAL_PHOTO
from .reference_resolver import ReferenceResolver
from .voice_brief_builder import VoiceBriefBuilder
from .trending_integration import TrendingIntelligence
from .vertical_registry import VerticalRegistry
from .debug_logger import PipelineDebugger
from app.services.llm_provider import LLMProvider, ChatMessage, get_llm_provider

logger = logging.getLogger(__name__)

# Flag to identify deep research mode
DEEP_RESEARCH_PROVIDERS = ['deep-research', 'deep_research']

# Platform configurations
PLATFORM_CONFIG = {
    'facebook': {
        'posts_per_week': 3,
        'posting_days': [0, 2, 4],      # Mon, Wed, Fri
        'posting_times': ['10:00', '10:00', '15:00'],
        'max_length_words': 100,
        'hashtag_count': 3,
        'tone': 'conversational, slightly provocative',
        'cta_style': 'question'
    },
    'linkedin': {
        'posts_per_week': 2,
        'posting_days': [1, 4],          # Tue, Fri
        'posting_times': ['09:00', '14:00'],
        'max_length_words': 150,
        'hashtag_count': 5,
        'tone': 'professional, insightful',
        'cta_style': 'thought-provoking question'
    },
    'twitter': {
        'posts_per_week': 5,
        'posting_days': [0, 1, 2, 3, 4], # Mon-Fri
        'posting_times': ['09:00', '12:00', '15:00', '18:00', '20:00'],
        'max_length_words': 50,
        'hashtag_count': 2,
        'tone': 'concise, witty',
        'cta_style': 'retweet prompt'
    },
    'instagram': {
        'posts_per_week': 3,
        'posting_days': [1, 3, 5],       # Tue, Thu, Sat
        'posting_times': ['12:00', '18:00', '20:00'],
        'max_length_words': 100,
        'hashtag_count': 10,
        'tone': 'visual, emotional',
        'cta_style': 'engagement prompt'
    }
}


class ContentEnginePipeline:
    """
    3-stage pipeline for content calendar generation.
    
    Usage:
        pipeline = ContentEnginePipeline(ai_provider=provider)
        result = pipeline.generate(
            business_context={...},
            platform='facebook',
            timeframe_weeks=4,
            start_date='2026-04-01',
            opportunities={...},
            instructions='Focus on AC installation'
        )
    """
    
    def __init__(self, ai_provider: LLMProvider = None, provider_name: str = None,
                 debug_level: str = None):
        self.ai_provider = ai_provider
        self.provider_name = provider_name or 'claude'
        self.config_resolver = ConfigResolver()
        self.reference_resolver = ReferenceResolver()
        self.voice_builder = VoiceBriefBuilder()
        self.trending = TrendingIntelligence()
        self.debug = PipelineDebugger(debug_level)
        self._load_training_docs()

    def _call_llm(self, provider: LLMProvider, prompt: str, temperature: float = 0.3) -> str:
        """Adapter: call the LLM provider and return raw text response."""
        messages = [ChatMessage(role="user", content=prompt)]
        response = provider.chat_completion(messages, temperature=temperature)
        return response.content

    def _load_training_docs(self):
        """Load the content type reference card and training master."""
        base_dir = os.path.join(os.path.dirname(__file__), 'prompts')

        # Reference card for Stage 1 (Strategist)
        ref_card_path = os.path.join(base_dir, 'content_type_reference_card.txt')
        try:
            with open(ref_card_path, 'r', encoding='utf-8') as f:
                self.reference_card = f.read()
            logger.info(f"Loaded content type reference card ({len(self.reference_card)} chars)")
        except FileNotFoundError:
            logger.warning(f"Content type reference card not found: {ref_card_path} — using empty")
            self.reference_card = ''

        # Training master for Stage 2 (Writer)
        training_path = os.path.join(base_dir, 'content_type_training_master.txt')
        try:
            with open(training_path, 'r', encoding='utf-8') as f:
                self.training_master_full = f.read()
            logger.info(f"Loaded content type training master ({len(self.training_master_full)} chars)")
        except FileNotFoundError:
            logger.warning(f"Content type training master not found: {training_path} — using empty")
            self.training_master_full = ''
        
        # Pre-parse training master into sections for targeted injection
        self._parse_training_sections()
    
    def _parse_training_sections(self):
        """Split training master into Section 1 (universal) and per-type sections."""
        text = self.training_master_full
        
        # Extract Section 1 (universal principles)
        s1_start = text.find('SECTION 1: UNIVERSAL PRINCIPLES')
        s2_start = text.find('SECTION 2: DEEP TRAINING EXAMPLES')
        s3_start = text.find('SECTION 3: TYPE IDENTITY CARDS')
        s4_start = text.find('SECTION 4: GLOBAL HARD RULES')
        
        self.training_section1 = text[s1_start:s2_start] if s1_start >= 0 and s2_start >= 0 else ''
        self.training_section4 = text[s4_start:] if s4_start >= 0 else ''
        
        # Extract individual type sections from Section 2 and 3
        self.type_training = {}
        
        # Deep training types (Section 2)
        section2_text = text[s2_start:s3_start] if s2_start >= 0 and s3_start >= 0 else ''
        for type_marker in ['TRANSFORMATION POST', 'HUMAN MOMENTS POST', 
                           'SOCIAL PROOF / CLIENT WIN POST', 'SCENARIO / STORY POST',
                           'AUTHORITY / OPINION POST']:
            start = section2_text.find(f'CONTENT TYPE: {type_marker}')
            if start >= 0:
                # Find next CONTENT TYPE or end of section
                next_start = section2_text.find('CONTENT TYPE:', start + 1)
                chunk = section2_text[start:next_start] if next_start >= 0 else section2_text[start:]
                # Map to our content type keys
                key_map = {
                    'TRANSFORMATION POST': 'transformation',
                    'HUMAN MOMENTS POST': 'human_moments',
                    'SOCIAL PROOF / CLIENT WIN POST': 'social_proof',
                    'SCENARIO / STORY POST': 'scenario_story',
                    'AUTHORITY / OPINION POST': 'authority_opinion'
                }
                key = key_map.get(type_marker)
                if key:
                    self.type_training[key] = chunk
        
        # Identity card types (Section 3)
        section3_text = text[s3_start:s4_start] if s3_start >= 0 and s4_start >= 0 else ''
        identity_markers = {
            'EDUCATIONAL / PRACTICAL VALUE': 'educational',
            'COMMUNITY / LOCAL': 'community',
            'SOFT PROMOTIONAL': 'soft_promotional',
            'BEHIND THE SCENES': 'behind_the_scenes',
            'ORIGIN NETWORK': 'origin_network',
            'SEASONAL / TIMELY': 'seasonal_timely',
        }
        for marker, key in identity_markers.items():
            start = section3_text.find(marker)
            if start >= 0:
                # Find the next identity card marker
                remaining = section3_text[start:]
                lines = remaining.split('\n')
                # Collect lines until next card (starts with all-caps word at beginning)
                chunk_lines = []
                for i, line in enumerate(lines):
                    if i == 0:
                        chunk_lines.append(line)
                        continue
                    # Check if this line starts a new identity card
                    stripped = line.strip()
                    if stripped and stripped == stripped.upper() and len(stripped) > 5 and '/' in stripped:
                        break
                    chunk_lines.append(line)
                self.type_training[key] = '\n'.join(chunk_lines)
        
        logger.info(f"Parsed training sections: {list(self.type_training.keys())}")

    @staticmethod
    def _normalize_content_type(ct: str) -> str:
        """Normalize display names like 'Seasonal / Timely' to keys like 'seasonal_timely'."""
        if ct in CONTENT_TYPES:
            return ct
        # Map display names to keys
        display_map = {
            'transformation': 'transformation', 'transformation post': 'transformation',
            'educational': 'educational', 'educational / practical value': 'educational',
            'educational/practical value': 'educational', 'practical value': 'educational',
            'social proof': 'social_proof', 'social proof / client win': 'social_proof',
            'social_proof / client win': 'social_proof', 'client win': 'social_proof',
            'community': 'community', 'community / local': 'community',
            'community/local': 'community', 'local': 'community',
            'soft promotional': 'soft_promotional', 'soft_promotional': 'soft_promotional',
            'promotional': 'soft_promotional',
            'behind the scenes': 'behind_the_scenes', 'behind_the_scenes': 'behind_the_scenes',
            'scenario / story': 'scenario_story', 'scenario/story': 'scenario_story',
            'scenario story': 'scenario_story', 'scenario': 'scenario_story',
            'authority / opinion': 'authority_opinion', 'authority/opinion': 'authority_opinion',
            'authority opinion': 'authority_opinion', 'authority': 'authority_opinion',
            'origin network': 'origin_network', 'origin_network': 'origin_network',
            'seasonal / timely': 'seasonal_timely', 'seasonal/timely': 'seasonal_timely',
            'seasonal timely': 'seasonal_timely', 'seasonal': 'seasonal_timely',
            'human moments': 'human_moments', 'human_moments': 'human_moments',
            'human moment': 'human_moments',
        }
        normalized = display_map.get(ct.lower().strip(), None)
        if normalized:
            return normalized
        logger.warning(f"Unknown content type '{ct}', defaulting to 'educational'")
        return 'educational'

    # ──────────────────────────────────────────────────────────────
    # MAIN ENTRY POINT
    # ──────────────────────────────────────────────────────────────
    
    def generate(self,
                 business_context: Dict[str, Any],
                 platform: str,
                 timeframe_weeks: int,
                 start_date: str,
                 opportunities: Dict[str, Any] = None,
                 instructions: str = '',
                 business_id: int = None,
                 recent_posts: List[Dict] = None,
                 vector_store_ids: List[str] = None) -> Dict[str, Any]:
        """
        Main pipeline entry point.
        
        Returns complete calendar response.
        """
        try:
            # ── STEP 0: Assemble Context ──
            self.debug.log_stage_start('Stage 0: Assemble Context')
            context = self._assemble_context(
                business_context=business_context,
                platform=platform,
                timeframe_weeks=timeframe_weeks,
                start_date=start_date,
                opportunities=opportunities,
                instructions=instructions,
                business_id=business_id,
                recent_posts=recent_posts,
                vector_store_ids=vector_store_ids
            )
            self.debug.log_context(context)
            self.debug.log_stage_end('Stage 0: Assemble Context')
            
            # ── STAGE 1: Strategist ──
            is_deep_research = self.provider_name.lower() in DEEP_RESEARCH_PROVIDERS
            
            self.debug.log_stage_start('Stage 1: Strategist')
            if is_deep_research:
                logger.info(f"Stage 1: DEEP RESEARCH Strategist")
                topics = self._stage1_deep_research(context)
            else:
                topics = self._stage1_strategist(context)
            self.debug.log_stage_end('Stage 1: Strategist', f'{len(topics)} topics')
            
            # ── STAGE 2: Writer ──
            # Deep research is great for topic discovery but Claude writes better posts
            if is_deep_research:
                logger.info("Stage 2: Switching to Claude for post writing")
                self._writer_provider = get_llm_provider('claude')
            else:
                self._writer_provider = self.ai_provider
            
            self.debug.log_stage_start('Stage 2: Writer')
            posts = self._stage2_writer_batch(topics, context)
            self.debug.log_stage_end('Stage 2: Writer', f'{len(posts)} posts written')
            
            # ── STAGE 3: Validator ──
            self.debug.log_stage_start('Stage 3: Validator')
            posts_before = len(posts)
            calendar = self._stage3_validator(posts, context)
            self.debug.log_validator(posts_before, calendar['total_posts'])
            self.debug.log_stage_end('Stage 3: Validator', f"{calendar['total_posts']} posts")
            
            return {
                'status': 'success',
                'calendar': calendar,
                'metadata': {
                    'platform': platform,
                    'vertical': context['vertical'],
                    'total_opportunities_analyzed': len(context['opportunity_summaries']),
                    'posts_generated': len(posts),
                    'timeframe_weeks': timeframe_weeks,
                    'content_type_distribution': self._calc_type_distribution(calendar['posts']),
                    'seasonal_triggers_active': [
                        t.get('focus', '') for t in context['resolved_config']['seasonal_triggers']
                    ],
                    'instructions_provided': bool(instructions),
                    'ai_provider': self.provider_name,
                    'deep_research_used': self.provider_name.lower() in DEEP_RESEARCH_PROVIDERS
                }
            }
            
        except Exception as e:
            logger.error(f"Pipeline failed: {str(e)}", exc_info=True)
            return {
                'status': 'error',
                'error': str(e),
                'calendar': None
            }

    # ──────────────────────────────────────────────────────────────
    # STEP 0: ASSEMBLE CONTEXT
    # ──────────────────────────────────────────────────────────────
    
    def _assemble_context(self, business_context, platform, timeframe_weeks,
                          start_date, opportunities, instructions, business_id,
                          recent_posts, vector_store_ids=None) -> Dict[str, Any]:
        """Assemble all context needed for the pipeline stages."""
        
        # Detect vertical
        vertical = self._detect_vertical(business_context)
        
        # Parse start date and target months
        try:
            start_dt = datetime.fromisoformat(start_date.replace('Z', '+00:00'))
        except:
            start_dt = datetime.now()
        
        end_dt = start_dt + timedelta(weeks=timeframe_weeks)
        target_months = list(set([start_dt.month, end_dt.month]))
        
        # Resolve config (vertical defaults + business overrides)
        resolved_config = self.config_resolver.resolve(
            vertical=vertical,
            business_id=business_id,
            target_months=target_months
        )
        
        # Platform config
        platform_cfg = PLATFORM_CONFIG.get(platform, PLATFORM_CONFIG['facebook'])
        posts_needed = platform_cfg['posts_per_week'] * timeframe_weeks
        
        # Build slim business summary for Stage 1
        business_summary = self.voice_builder.build_slim_summary(business_context)
        
        # Build rich voice brief for Stage 2
        merag_data = business_context.get('merag_data', {})
        voice_brief = self.voice_builder.build(
            business_context=business_context,
            merag_data=merag_data,
            instructions=instructions or '',
        )
        
        # Extract opportunity summaries (slim format for Stage 1)
        opportunity_summaries = self._extract_opportunity_summaries(opportunities or {})
        
        # Fetch trending intelligence (placeholder — returns empty until API is connected)
        trending_data = self.trending.fetch_all(vertical=vertical, platform=platform)
        
        # Get curated items from DB
        curated_topics = self.reference_resolver.get_curated_topics(vertical)
        
        return {
            'vertical': vertical,
            'business_id': business_id,
            'resolved_config': resolved_config,
            'platform': platform,
            'platform_config': platform_cfg,
            'posts_needed': posts_needed,
            'start_dt': start_dt,
            'end_dt': end_dt,
            'target_months': target_months,
            'business_summary': business_summary,
            'voice_brief': voice_brief,
            'business_context': business_context,
            'opportunity_summaries': opportunity_summaries,
            'trending_data': trending_data,
            'curated_topics': curated_topics,
            'instructions': instructions or '',
            'recent_posts': recent_posts or [],
            'vector_store_ids': vector_store_ids or [],
        }
    
    def _detect_vertical(self, business_context: Dict) -> str:
        """
        Detect vertical from business context using the Vertical Registry.
        
        The registry auto-discovers verticals from the Trending API
        and resolves names via exact match, aliases, or fuzzy matching.
        No hardcoded keyword maps needed.
        """
        registry = VerticalRegistry()
        result = registry.resolve_from_context(business_context)
        if result:
            vertical_name = result['name'].lower()
            logger.info(f"Vertical detected: {vertical_name} (id={result['id']})")
            return vertical_name
        
        logger.warning("Could not detect vertical from business context, using 'professional-services'")
        return 'professional-services'
    
    def _extract_opportunity_summaries(self, input_data: Dict) -> List[Dict]:
        """Extract slim opportunity summaries from the full input data."""
        summaries = []
        
        # Products & their categories
        products = input_data.get('products_and_services', [])
        if not products or not isinstance(products, list):
            products = []
        
        for product in products:
            if not product or not isinstance(product, dict):
                continue
            product_name = product.get('product_name', '')
            
            for category in (product.get('categories', []) or []):
                if not category or not isinstance(category, dict):
                    continue
                cat_type = category.get('category', '')
                
                if cat_type == 'news_items':
                    for item in (category.get('titles', []) or []):
                        if item and isinstance(item, dict) and item.get('title'):
                            summaries.append({
                                'source': 'news',
                                'title': item['title'][:200],
                                'snippet': (item.get('snippet') or '')[:150],
                                'product': product_name
                            })
                
                elif cat_type == 'audience_questions':
                    for item in (category.get('titles') or category.get('keywords') or []):
                        if item and isinstance(item, dict) and item.get('keyword'):
                            summaries.append({
                                'source': 'question',
                                'title': item['keyword'],
                                'product': product_name
                            })
                
                elif category.get('keywords'):
                    for kg in (category.get('keywords', []) or []):
                        if not kg or not isinstance(kg, dict):
                            continue
                        for title in (kg.get('titles', []) or []):
                            if title and isinstance(title, dict) and title.get('title'):
                                summaries.append({
                                    'source': 'keyword',
                                    'title': title['title'][:200],
                                    'keyword': kg.get('keyword', ''),
                                    'product': product_name
                                })
        
        # Competitor titles
        competitors = input_data.get('competitors', {})
        if competitors and isinstance(competitors, dict):
            for item in (competitors.get('titles', []) or []):
                if item and isinstance(item, dict) and item.get('title'):
                    summaries.append({
                        'source': 'competitor',
                        'title': item['title'][:200],
                    })
        
        # Business titles
        business = input_data.get('business', {})
        if business and isinstance(business, dict):
            for item in (business.get('titles', []) or []):
                if item and isinstance(item, dict) and item.get('title'):
                    summaries.append({
                        'source': 'business',
                        'title': item['title'][:200],
                    })
        
        logger.info(f"Extracted {len(summaries)} opportunity summaries")
        return summaries

    def _format_trending_for_strategist(self, trending_data: Dict) -> str:
        """Format trending intelligence data for the Stage 1 prompt."""
        sections = []
        
        # Trending topics
        topics = trending_data.get('topics', [])
        if topics:
            lines = ["\nTRENDING TOPICS (real-time signals — use for timely content):"]
            for t in topics[:10]:
                growth = f" (+{t.get('growth_percent', 0)}%)" if t.get('growth_percent') else ""
                lines.append(f"  - {t.get('topic', '')}{growth}")
            sections.append('\n'.join(lines))
        
        # Industry news
        news = trending_data.get('news', [])
        if news:
            lines = ["\nINDUSTRY NEWS (timely triggers):"]
            for n in news[:5]:
                score = f" (relevance: {n.get('relevance_score', '')})" if n.get('relevance_score') else ""
                lines.append(f"  - {n.get('title', '')}{score} — {n.get('source', '')}")
            sections.append('\n'.join(lines))
        
        # Viral social posts as topic inspiration
        pulse = trending_data.get('social_pulse', [])
        if pulse:
            lines = ["\nVIRAL CONTENT RIGHT NOW (topic inspiration — what audiences engage with):"]
            for p in pulse[:5]:
                views = p.get('engagement', {}).get('views', 0)
                views_str = f" ({views:,} views)" if views else ""
                lines.append(f"  - \"{p.get('post_text', '')[:120]}\"{views_str}")
            sections.append('\n'.join(lines))
        
        return '\n'.join(sections) if sections else ""

    # ──────────────────────────────────────────────────────────────
    # STAGE 1: STRATEGIST
    # ──────────────────────────────────────────────────────────────
    
    def _stage1_strategist(self, ctx: Dict) -> List[Dict]:
        """
        AI Call #1: Pick topics from opportunities and assign content types.
        """
        # Build the strategist prompt
        config = ctx['resolved_config']
        
        # Format content type weights for the prompt
        weights_str = '\n'.join([
            f"  - {ct}: {int(w * 100)}%"
            for ct, w in config['content_type_weights'].items()
            if w > 0
        ])
        
        # Format seasonal triggers
        seasonal_str = "None active for this period."
        if config['seasonal_triggers']:
            seasonal_str = '\n'.join([
                f"  - {t['focus']} (Hook: {t.get('hook', 'N/A')})"
                for t in config['seasonal_triggers'][:5]
            ])
        
        # Format recent posts for dedup
        dedup_str = "No recent posts on record."
        if ctx['recent_posts']:
            dedup_str = '\n'.join([
                f"  - \"{p.get('title', 'untitled')}\" ({p.get('content_type', 'unknown')}, {p.get('publication_date', 'unknown')})"
                for p in ctx['recent_posts'][:20]
            ])
        
        # Format opportunities (limit to prevent overwhelming)
        opps = ctx['opportunity_summaries'][:40]  # Cap at 40
        opps_by_source = {}
        for opp in opps:
            src = opp.get('source', 'other')
            if src not in opps_by_source:
                opps_by_source[src] = []
            opps_by_source[src].append(opp)
        
        opps_str = ''
        for src, items in opps_by_source.items():
            opps_str += f"\n{src.upper()} ({len(items)} items):\n"
            for item in items[:10]:
                opps_str += f"  - {item.get('title', '')}  [product: {item.get('product', 'general')}]\n"
        
        # Format trending intelligence
        trending_str = self._format_trending_for_strategist(ctx['trending_data'])
        
        # When no opportunities exist, trending becomes the primary source
        if not opps_str:
            if trending_str:
                opps_str = (
                    "No pre-researched opportunities available. "
                    "Use the TRENDING DATA below as your PRIMARY source material. "
                    "Also create original topics from the business context and seasonal triggers."
                )
            else:
                opps_str = (
                    "No pre-researched opportunities or trending data available. "
                    "Generate original topics from the business context, industry knowledge, "
                    "and seasonal triggers. Be specific — use real scenarios, common pain points, "
                    "and industry-relevant situations."
                )
        
        # Format curated topics (human-pinned must-use topics)
        curated_str = ""
        if ctx['curated_topics']:
            curated_str = "\nCURATED PICKS (human-selected — use these directly):\n"
            for item in ctx['curated_topics']:
                ct_tag = f" → tagged as {item['tagged_content_type']}" if item.get('tagged_content_type') else ""
                notes = f" | Notes: {item['notes']}" if item.get('notes') else ""
                curated_str += f"  - {item['content']}{ct_tag}{notes}\n"
        
        # Instructions (highest priority)
        instructions_block = ""
        if ctx['instructions']:
            instructions_block = f"""
CALLER INSTRUCTIONS (HIGHEST PRIORITY — follow these first):
{ctx['instructions']}
"""

        prompt = f"""{instructions_block}

You are a content strategist selecting topics for a {ctx['platform']} social media calendar.

BUSINESS:
{ctx['business_summary']}

CONTENT TYPE SYSTEM:
{self.reference_card}

TARGET DISTRIBUTION FOR THIS VERTICAL ({ctx['vertical']}):
{weights_str}

SEASONAL TRIGGERS ACTIVE:
{seasonal_str}

AVAILABLE OPPORTUNITIES:
{opps_str}
{trending_str}
{curated_str}
DEDUPLICATION — DO NOT repeat these recent topics:
{dedup_str}

TASK:
Select exactly {ctx['posts_needed']} topics for a {ctx['platform']} calendar.
For each topic, assign a content type from the enabled list above.
At least 1-2 posts MUST use active seasonal triggers (if any).
Follow the target distribution weights as closely as possible.
Each topic must be unique — no duplicates.

Return ONLY valid JSON array:
[
  {{
    "theme_title": "descriptive title of the post topic",
    "content_type": "one of the 11 types",
    "target_emotion": "the primary emotion",
    "hook_direction": "brief guidance for the writer on how to open this post",
    "source": "news|question|keyword|competitor|business|seasonal|original",
    "source_title": "original title from opportunity data if applicable",
    "product_focus": "which product/service this relates to",
    "requires_real_photo": true/false
  }}
]
"""

        self.debug.log_strategist_prompt(prompt)

        response = self._call_llm(self.ai_provider, prompt, temperature=0.4)

        # Parse response
        try:
            import re
            json_match = re.search(r'\[[\s\S]*\]', response)
            if json_match:
                topics = json.loads(json_match.group())
            else:
                topics = json.loads(response)
        except json.JSONDecodeError as e:
            logger.error(f"Stage 1 JSON parse failed: {str(e)}\nResponse: {response[:500]}")
            raise ValueError(f"Strategist returned invalid JSON: {str(e)}")
        
        # Validate and normalize content types
        for topic in topics:
            ct = topic.get('content_type', '')
            ct = self._normalize_content_type(ct)
            topic['content_type'] = ct
            topic['requires_real_photo'] = ct in REQUIRES_REAL_PHOTO
        
        self.debug.log_strategist_response(response, topics)
        return topics

    # ──────────────────────────────────────────────────────────────
    # STAGE 1 (ALT): DEEP RESEARCH STRATEGIST
    # ──────────────────────────────────────────────────────────────

    def _stage1_deep_research(self, ctx: Dict) -> List[Dict]:
        """
        Deep Research Stage 1: Use o3/o4-mini with web search to discover
        topics AND assign content types. Outputs same JSON format as regular
        strategist so Stage 2+3 work unchanged.
        """
        config = ctx['resolved_config']
        bc = ctx['business_context']

        weights_str = '\n'.join([
            f"  - {ct}: {int(w * 100)}%"
            for ct, w in config['content_type_weights'].items()
            if w > 0
        ])

        seasonal_str = "None active for this period."
        if config['seasonal_triggers']:
            seasonal_str = '\n'.join([
                f"  - {t['focus']} (Hook: {t.get('hook', 'N/A')})"
                for t in config['seasonal_triggers'][:5]
            ])

        dedup_str = "No recent posts on record."
        if ctx['recent_posts']:
            dedup_str = '\n'.join([
                f"  - \"{p.get('title', 'untitled')}\" ({p.get('content_type', 'unknown')})"
                for p in ctx['recent_posts'][:20]
            ])

        instructions_block = ""
        if ctx['instructions']:
            instructions_block = f"CALLER INSTRUCTIONS (HIGHEST PRIORITY):\n{ctx['instructions']}\n"

        business_website = bc.get('business_website', '') or bc.get('website', '')
        website_line = f"\nRESEARCH THIS WEBSITE: {business_website}" if business_website else ""

        # Include caller's opportunity data so deep research ADDS to it, not ignores it
        opps = ctx['opportunity_summaries'][:40]
        opps_by_source = {}
        for opp in opps:
            src = opp.get('source', 'other')
            if src not in opps_by_source:
                opps_by_source[src] = []
            opps_by_source[src].append(opp)

        opps_str = ''
        for src, items in opps_by_source.items():
            opps_str += f"\n{src.upper()} ({len(items)} items):\n"
            for item in items[:10]:
                opps_str += f"  - {item.get('title', '')}  [product: {item.get('product', 'general')}]\n"

        if not opps_str:
            opps_str = "No pre-researched data provided. Rely entirely on your web research."

        prompt = f"""{instructions_block}

You are a content strategist with web search access. Research and discover the
BEST possible topics for a {ctx['platform']} social media calendar.

BUSINESS:
{ctx['business_summary']}{website_line}

INDUSTRY: {bc.get('industry', 'General')}
LOCATION: {bc.get('location', 'United States')}

PRE-RESEARCHED DATA (use these as starting points, enhance with your web research):
{opps_str}

RESEARCH INSTRUCTIONS:
1. Use the pre-researched data above as a foundation
2. Search the web for recent news, trends, and developments that COMPLEMENT the data above
3. Look for local events and timely topics in {bc.get('location', 'the area')}
4. Research competitor content to find gaps and opportunities
5. Find audience questions and pain points discussed online
6. Prioritize topics where you can add SPECIFIC facts, stats, or recent developments from web research

CONTENT TYPE SYSTEM:
{self.reference_card}

TARGET DISTRIBUTION ({ctx['vertical']}):
{weights_str}

SEASONAL TRIGGERS ACTIVE:
{seasonal_str}

DEDUPLICATION — DO NOT repeat these:
{dedup_str}

TASK:
Discover and select exactly {ctx['posts_needed']} topics.
Assign a content type to each. Follow distribution weights.
At least 1-2 posts MUST use seasonal triggers (if any).
Include specific facts/stats from your research in hook_direction.

Return ONLY valid JSON array:
[
  {{
    "theme_title": "descriptive title",
    "content_type": "one of the 11 types",
    "target_emotion": "primary emotion",
    "hook_direction": "guidance with specific facts/stats from research",
    "source": "news|question|keyword|competitor|business|seasonal|original|research",
    "source_title": "original source or article title",
    "product_focus": "which product/service",
    "requires_real_photo": true/false
  }}
]
"""

        logger.info("[DeepResearch] Stage 1: calling AI provider with web search enabled")

        try:
            import time as _time
            _start = _time.time()
            output_text = self._call_llm(self.ai_provider, prompt, temperature=0.4)
            elapsed = (_time.time() - _start) / 60
            logger.info(f"[DeepResearch] Stage 1 completed in {elapsed:.1f} minutes, response length={len(output_text)}")
        except Exception as e:
            logger.error(f"[DeepResearch] Stage 1 failed: {type(e).__name__}: {e}")
            raise

        # Remove citation markers from web search results
        try:
            import re as _re
            output_text = _re.sub(r'【[^】]*】', '', output_text)
        except Exception:
            pass

        # Parse JSON — same format as regular strategist
        try:
            import re
            json_match = re.search(r'\[[\s\S]*\]', output_text)
            if json_match:
                topics = json.loads(json_match.group())
            else:
                topics = json.loads(output_text)
        except json.JSONDecodeError as e:
            logger.error(f"[DeepResearch] JSON parse failed: {e}\nRaw output (first 500 chars): {output_text[:500]}")
            raise ValueError(f"Deep research returned invalid JSON: {str(e)}")

        # Validate and normalize content types
        for topic in topics:
            ct = topic.get('content_type', '')
            ct = self._normalize_content_type(ct)
            topic['content_type'] = ct
            topic['requires_real_photo'] = ct in REQUIRES_REAL_PHOTO

        return topics

    # ──────────────────────────────────────────────────────────────
    # STAGE 2: WRITER
    # ──────────────────────────────────────────────────────────────
    
    def _stage2_writer(self, topics: List[Dict], ctx: Dict) -> List[Dict]:
        """
        Write each post one at a time with focused context.
        """
        posts = []
        
        for idx, topic in enumerate(topics):
            try:
                post = self._write_single_post(topic, ctx, idx + 1)
                posts.append(post)
            except Exception as e:
                logger.error(f"Failed to write post {idx + 1} ({topic.get('theme_title')}): {str(e)}")
                raise
        
        return posts
    
    def _write_single_post(self, topic: Dict, ctx: Dict, post_number: int) -> Dict:
        """Write a single post using reference library approach."""
        
        content_type = topic.get('content_type', 'educational')
        pcfg = ctx['platform_config']
        
        # Layer A: Content type brief (what the post's JOB is)
        writer_context = self.reference_resolver.build_writer_context(
            content_type=content_type,
            vertical=ctx['vertical'],
            platform=ctx['platform'],
            trending_social_pulse=ctx['trending_data'].get('social_pulse', []),
            trending_hashtags=ctx['trending_data'].get('hashtags', []),
        )
        
        type_brief = writer_context['type_brief']
        style_refs_text = self.reference_resolver.format_style_references_for_prompt(
            writer_context['style_references']
        )
        
        self.debug.log_writer_context(
            post_number, 
            'learnings' if 'WHAT MAKES THIS POST WORK' in type_brief else 'static/default',
            len(writer_context['style_references']),
            len(writer_context['trending_hashtags'])
        )
        
        # Trending hashtags
        hashtag_guidance = ''
        if writer_context['trending_hashtags']:
            hashtag_guidance = f"\nTRENDING HASHTAGS (use where relevant): {', '.join(writer_context['trending_hashtags'][:10])}"
        
        # Seasonal context
        seasonal_context = ""
        if content_type == 'seasonal_timely' and ctx['resolved_config']['seasonal_triggers']:
            triggers = ctx['resolved_config']['seasonal_triggers']
            seasonal_context = "\nSEASONAL CONTEXT:\n" + '\n'.join([
                f"- {t['focus']}\n  Hook angle: {t.get('hook', 'N/A')}"
                for t in triggers[:3]
            ])
        
        prompt = f"""Write a {ctx['platform']} post.

=== THIS POST'S JOB ({content_type.upper()}) ===
{type_brief}

=== STYLE REFERENCES (what gets engagement in this industry — match this energy) ===
{style_refs_text}

=== WHO YOU ARE ===
{ctx['voice_brief']}

=== YOUR ASSIGNMENT ===
Topic: {topic.get('theme_title', '')}
Target emotion: {topic.get('target_emotion', '')}
Hook direction: {topic.get('hook_direction', '')}
Product focus: {topic.get('product_focus', '')}
{seasonal_context}

=== CONSTRAINTS ===
Platform: {ctx['platform']}
Max length: {pcfg['max_length_words']} words
Hashtags: exactly {pcfg['hashtag_count']}{hashtag_guidance}
Tone: {pcfg['tone']}
CTA style: {pcfg['cta_style']}
Never open with the business name
No URLs in post body
No "we are proud to" or "we specialize in"

Write a post that belongs in the style references collection above.

Return ONLY valid JSON:
{{
  "title": "short title for the post",
  "content": "the full post text (no hashtags here)",
  "hashtags": ["tag1", "tag2", "tag3"],
  "engagement_question": "optional question to drive comments",
  "visual_direction": "what photo/image to use (mark REAL CAPTURE REQUIRED if content type requires real photo)",
  "content_type": "{content_type}",
  "requires_real_photo": {str(topic.get('requires_real_photo', False)).lower()}
}}
"""

        self.debug.log_writer_prompt(post_number, content_type, prompt)

        # Use _writer_provider if set (deep research mode switches to claude for writing)
        writer = getattr(self, '_writer_provider', self.ai_provider)

        response = self._call_llm(writer, prompt, temperature=0.7)
        
        try:
            import re
            json_match = re.search(r'\{[\s\S]*\}', response)
            if json_match:
                post_data = json.loads(json_match.group())
            else:
                post_data = json.loads(response)
        except json.JSONDecodeError as e:
            logger.error(f"Stage 2 JSON parse failed for post {post_number}: {str(e)}")
            raise ValueError(f"Writer returned invalid JSON for post {post_number}: {str(e)}")
        
        # Append hashtags to content
        content = post_data.get('content', '')
        hashtags = post_data.get('hashtags', [])
        if hashtags:
            hashtag_str = ' '.join(f'#{tag}' if not tag.startswith('#') else tag for tag in hashtags)
            content = f"{content}\n\n{hashtag_str}"
        
        result = {
            'title': post_data.get('title', topic.get('theme_title', '')),
            'content': content,
            'hashtags': hashtags,
            'engagement_question': post_data.get('engagement_question', ''),
            'visual_direction': post_data.get('visual_direction', ''),
            'content_type': content_type,
            'requires_real_photo': topic.get('requires_real_photo', False),
            'target_emotion': topic.get('target_emotion', ''),
            'source': topic.get('source', ''),
            'source_title': topic.get('source_title', ''),
            'product_focus': topic.get('product_focus', ''),
            'theme_title': topic.get('theme_title', ''),
        }
        self.debug.log_writer_response(post_number, response, result)
        return result

    def _stage2_writer_batch(self, topics: List[Dict], ctx: Dict) -> List[Dict]:
        """
        Write ALL posts in a single AI call.
        
        Prompt layers:
            1. Learnings brief (what patterns work — from content-fine-tuning service)
            2. Training master (how to write each type — examples, anti-patterns)
            3. Style references (trending viral posts — what's working in the wild)
            4. Voice brief (who the business is)
            5. Assignments (topics from Stage 1)
        """
        writer = getattr(self, '_writer_provider', self.ai_provider)
        pcfg = ctx['platform_config']

        # ── Layer 1: Learnings brief per content type ──
        used_types = list(set(t.get('content_type', 'educational') for t in topics))
        briefs_parts = []
        for ct in used_types:
            brief = self.reference_resolver.get_type_brief(
                ct, vertical=ctx['vertical'], platform=ctx['platform']
            )
            briefs_parts.append(f"{ct.upper()}:\n{brief}")
        briefs_block = '\n\n'.join(briefs_parts)

        # ── Layer 2: Training master sections per content type ──
        training_parts = []
        for ct in used_types:
            section = self.type_training.get(ct, '')
            if section:
                training_parts.append(section.strip())
        training_block = '\n\n---\n\n'.join(training_parts) if training_parts else ''
        
        # Also include universal principles (Section 1) — truncated to key rules
        universal_block = ''
        if self.training_section1:
            # Take first ~2000 chars of universal principles (hook, emotion, business voice)
            universal_block = self.training_section1[:2000].strip()

        # ── Layer 3: Style references (trending viral posts + DB + curated) ──
        writer_context = self.reference_resolver.build_writer_context(
            content_type='educational',  # doesn't matter — refs are by vertical
            vertical=ctx['vertical'],
            platform=ctx['platform'],
            trending_social_pulse=ctx['trending_data'].get('social_pulse', []),
            trending_hashtags=ctx['trending_data'].get('hashtags', []),
        )
        style_refs_text = self.reference_resolver.format_style_references_for_prompt(
            writer_context['style_references']
        )
        
        self.debug.log_writer_context(
            0,  # batch
            'learnings' if any('WHAT MAKES THIS POST WORK' in b for b in briefs_parts) else 'static/default',
            len(writer_context['style_references']),
            len(writer_context['trending_hashtags'])
        )

        # Trending hashtags
        hashtag_guidance = ''
        if writer_context['trending_hashtags']:
            hashtag_guidance = f"\nTRENDING HASHTAGS: {', '.join(writer_context['trending_hashtags'][:10])}"

        # ── Build assignments block ──
        assignments = []
        for idx, topic in enumerate(topics, 1):
            content_type = topic.get('content_type', 'educational')
            seasonal_note = ""
            if content_type == 'seasonal_timely' and ctx['resolved_config']['seasonal_triggers']:
                triggers = ctx['resolved_config']['seasonal_triggers']
                seasonal_note = f"\n    Seasonal context: {triggers[0].get('focus', '')}" if triggers else ""

            assignments.append(
                f"POST {idx}:\n"
                f"    Topic: {topic.get('theme_title', '')}\n"
                f"    Content type: {content_type}\n"
                f"    Target emotion: {topic.get('target_emotion', '')}\n"
                f"    Hook direction: {topic.get('hook_direction', '')}\n"
                f"    Product focus: {topic.get('product_focus', '')}\n"
                f"    Requires real photo: {topic.get('requires_real_photo', False)}"
                f"{seasonal_note}"
            )

        assignments_block = '\n\n'.join(assignments)

        # ── Assemble prompt with all layers ──
        prompt_parts = [f"Write {len(topics)} {ctx['platform']} posts.\n"]
        
        # Universal writing principles
        if universal_block:
            prompt_parts.append(f"=== WRITING PRINCIPLES ===\n{universal_block}\n")
        
        # Per-type learnings
        prompt_parts.append(f"=== CONTENT TYPE JOBS (what patterns work) ===\n{briefs_block}\n")
        
        # Per-type training examples
        if training_block:
            prompt_parts.append(f"=== TRAINING: HOW TO WRITE EACH TYPE (study these examples) ===\n{training_block}\n")
        
        # Style references from trending/DB
        prompt_parts.append(f"=== STYLE REFERENCES (match this energy) ===\n{style_refs_text}\n")
        
        # Voice
        prompt_parts.append(f"=== WHO YOU ARE ===\n{ctx['voice_brief']}\n")
        
        # Assignments
        prompt_parts.append(f"=== ASSIGNMENTS ===\n{assignments_block}\n")
        
        # Constraints
        prompt_parts.append(f"""=== CONSTRAINTS ===
Platform: {ctx['platform']}
Max length per post: {pcfg['max_length_words']} words
Hashtags per post: exactly {pcfg['hashtag_count']}{hashtag_guidance}
Tone: {pcfg['tone']}
CTA style: {pcfg['cta_style']}
Never open with the business name
No URLs in post body
No "we are proud to" or "we specialize in"
Each post must use a different character name — variety across the calendar
Use specific facts/stats from hook_direction — do NOT make up numbers

Write posts that belong in the style references collection above.

Return ONLY a valid JSON array with {len(topics)} objects:
[
  {{
    "post_number": 1,
    "title": "short title",
    "content": "full post text (no hashtags)",
    "hashtags": ["tag1", "tag2", "tag3"],
    "engagement_question": "question to drive comments",
    "visual_direction": "photo/image guidance (mark REAL CAPTURE REQUIRED where needed)"
  }}
]
""")        
        prompt = '\n'.join(prompt_parts)

        self.debug.log_batch_prompt(len(topics), prompt)

        response = self._call_llm(writer, prompt, temperature=0.7)

        # Parse response
        try:
            import re
            json_match = re.search(r'\[[\s\S]*\]', response)
            if json_match:
                post_list = json.loads(json_match.group())
            else:
                post_list = json.loads(response)
        except json.JSONDecodeError as e:
            logger.error(f"Stage 2 batch JSON parse failed: {str(e)}")
            raise ValueError(f"Batch writer returned invalid JSON: {str(e)}")

        # Map back to full post format
        posts = []
        for idx, post_data in enumerate(post_list):
            topic = topics[idx] if idx < len(topics) else {}
            content_type = topic.get('content_type', 'educational')

            content = post_data.get('content', '')
            hashtags = post_data.get('hashtags', [])
            if hashtags:
                hashtag_str = ' '.join(f'#{tag}' if not tag.startswith('#') else tag for tag in hashtags)
                content = f"{content}\n\n{hashtag_str}"

            posts.append({
                'title': post_data.get('title', topic.get('theme_title', '')),
                'content': content,
                'hashtags': hashtags,
                'engagement_question': post_data.get('engagement_question', ''),
                'visual_direction': post_data.get('visual_direction', ''),
                'content_type': content_type,
                'requires_real_photo': topic.get('requires_real_photo', False),
                'target_emotion': topic.get('target_emotion', ''),
                'source': topic.get('source', ''),
                'source_title': topic.get('source_title', ''),
                'product_focus': topic.get('product_focus', ''),
                'theme_title': topic.get('theme_title', ''),
            })

        self.debug.log_batch_response(response, posts)
        return posts

    # ──────────────────────────────────────────────────────────────
    # STAGE 3: VALIDATOR
    # ──────────────────────────────────────────────────────────────
    
    def _stage3_validator(self, posts: List[Dict], ctx: Dict) -> Dict:
        """
        Enforce rules, reorder if needed, assign dates.
        Pure code — no AI calls.
        """
        if not posts:
            return self._empty_calendar(ctx)
        
        # Rule 1: No two consecutive same content types — swap if found
        posts = self._fix_consecutive_types(posts)
        
        # Rule 2: Max 20% soft promotional
        posts = self._enforce_promo_limit(posts)
        
        # Rule 3: Max 2 origin_network per month
        posts = self._enforce_origin_limit(posts)
        
        # Assign dates
        calendar_posts = self._assign_dates(posts, ctx)
        
        bc = ctx['business_context']
        return {
            'platform': ctx['platform'],
            'business_name': bc.get('business_name', 'Business'),
            'start_date': ctx['start_dt'].strftime('%Y-%m-%d'),
            'end_date': ctx['end_dt'].strftime('%Y-%m-%d'),
            'total_posts': len(calendar_posts),
            'posts': calendar_posts,
            'posting_schedule': {
                'frequency': f"{ctx['platform_config']['posts_per_week']} posts per week",
                'days': [
                    ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday'][d]
                    for d in ctx['platform_config']['posting_days']
                ],
                'optimal_times': ctx['platform_config']['posting_times']
            },
            'content_type_distribution': self._calc_type_distribution(calendar_posts)
        }
    
    def _fix_consecutive_types(self, posts: List[Dict]) -> List[Dict]:
        """Swap posts to avoid two consecutive same content types."""
        changed = True
        max_iterations = len(posts) * 2
        iterations = 0
        
        while changed and iterations < max_iterations:
            changed = False
            iterations += 1
            for i in range(len(posts) - 1):
                if posts[i]['content_type'] == posts[i + 1]['content_type']:
                    # Find a post later in the list with a different type to swap
                    for j in range(i + 2, len(posts)):
                        if posts[j]['content_type'] != posts[i]['content_type']:
                            posts[i + 1], posts[j] = posts[j], posts[i + 1]
                            changed = True
                            break
        
        return posts
    
    def _enforce_promo_limit(self, posts: List[Dict]) -> List[Dict]:
        """Ensure max 20% are soft_promotional."""
        max_promo = max(1, int(len(posts) * 0.20))
        promo_count = 0
        result = []
        
        for post in posts:
            if post['content_type'] == 'soft_promotional':
                promo_count += 1
                if promo_count > max_promo:
                    logger.warning(f"Dropping excess promotional post: {post.get('title', '')}")
                    continue
            result.append(post)
        
        return result
    
    def _enforce_origin_limit(self, posts: List[Dict]) -> List[Dict]:
        """Ensure max 2 origin_network posts."""
        origin_count = 0
        result = []
        
        for post in posts:
            if post['content_type'] == 'origin_network':
                origin_count += 1
                if origin_count > 2:
                    logger.warning(f"Dropping excess origin network post: {post.get('title', '')}")
                    continue
            result.append(post)
        
        return result
    
    def _assign_dates(self, posts: List[Dict], ctx: Dict) -> List[Dict]:
        """Assign publication dates and times to posts."""
        pcfg = ctx['platform_config']
        posting_days = pcfg['posting_days']
        posting_times = pcfg['posting_times']
        start = ctx['start_dt']
        timeframe_weeks = (ctx['end_dt'] - start).days // 7
        
        calendar_posts = []
        post_idx = 0
        
        for week in range(timeframe_weeks):
            week_start = start + timedelta(weeks=week)
            
            for day_idx, day_offset in enumerate(posting_days):
                if post_idx >= len(posts):
                    break
                
                post_date = week_start + timedelta(days=day_offset)
                time_str = posting_times[day_idx % len(posting_times)]
                
                calendar_post = {
                    'publication_date': post_date.strftime('%Y-%m-%d'),
                    'publication_time': time_str,
                    'week_number': week + 1,
                    'day_of_week': post_date.strftime('%A').lower(),
                    **posts[post_idx]
                }
                calendar_posts.append(calendar_post)
                post_idx += 1
            
            if post_idx >= len(posts):
                break
        
        return calendar_posts
    
    def _calc_type_distribution(self, posts: List[Dict]) -> Dict[str, str]:
        """Calculate content type distribution as percentages."""
        if not posts:
            return {}
        
        counts = {}
        for post in posts:
            ct = post.get('content_type', 'unknown')
            counts[ct] = counts.get(ct, 0) + 1
        
        total = len(posts)
        return {k: f"{(v / total) * 100:.1f}%" for k, v in sorted(counts.items())}
    
    def _empty_calendar(self, ctx: Dict) -> Dict:
        """Return an empty calendar structure."""
        return {
            'platform': ctx['platform'],
            'business_name': ctx['business_context'].get('business_name', 'Business'),
            'start_date': ctx['start_dt'].strftime('%Y-%m-%d'),
            'end_date': ctx['end_dt'].strftime('%Y-%m-%d'),
            'total_posts': 0,
            'posts': [],
            'posting_schedule': {
                'frequency': '0 posts per week',
                'days': [],
                'optimal_times': []
            },
            'content_type_distribution': {}
        }

"""
Content Engine — Voice Brief Builder

Builds a rich business voice brief from multiple data sources.
Replaces the thin 3-4 sentence business summary with a personality-rich brief
that tells the AI WHO it's writing as.

Output format:
    WHO WE ARE: [name] — [years], [size], [vibe]
    HOW WE TALK: [tone description]
    WHAT MAKES US US: [unique truth]
    PROOF POINTS: [specific numbers, awards, metrics]
    OUR PEOPLE: [named team members + one detail each]
"""

from typing import Dict, Any, Optional
import logging

logger = logging.getLogger(__name__)


class VoiceBriefBuilder:
    """
    Builds a business voice brief from multiple sources.
    
    Usage:
        builder = VoiceBriefBuilder()
        brief = builder.build(
            business_context={...},
            merag_data={...},
            instructions="We just hired Marcus...",
            tone_override="Blue-collar honest"
        )
    """
    
    def build(self, business_context: Dict[str, Any],
              merag_data: Dict[str, Any] = None,
              instructions: str = '',
              tone_override: str = None) -> str:
        """
        Build the voice brief from all available sources.
        
        Returns a formatted string ready for prompt injection.
        """
        bc = business_context
        merag = merag_data or {}
        
        # WHO WE ARE
        who = self._build_who(bc, merag)
        
        # HOW WE TALK
        how = self._build_tone(bc, tone_override)
        
        # WHAT MAKES US US
        what = self._build_differentiator(bc)
        
        # PROOF POINTS
        proof = self._build_proof_points(bc, merag, instructions)
        
        # OUR PEOPLE
        people = self._build_people(bc, instructions, merag)
        
        sections = [
            f"WHO WE ARE: {who}",
            f"HOW WE TALK: {how}",
            f"WHAT MAKES US US: {what}",
        ]
        
        if proof:
            sections.append(f"PROOF POINTS: {proof}")
        
        if people:
            sections.append(f"OUR PEOPLE: {people}")
        
        return '\n'.join(sections)
    
    def _build_who(self, bc: Dict, merag: Dict) -> str:
        """Build the identity line."""
        name = bc.get('business_name', 'Business')
        industry = bc.get('industry', '')
        location = bc.get('location', '')
        desc = bc.get('business_description', '')
        
        parts = [name]
        if industry:
            parts.append(f"a {industry} business")
        if location:
            parts.append(f"in {location}")
        
        # Try to extract years/size from description
        if desc:
            first_sentence = desc.split('.')[0] + '.' if '.' in desc else desc[:150]
            parts.append(f"— {first_sentence}")
        
        return ' '.join(parts)
    
    def _build_tone(self, bc: Dict, tone_override: str = None) -> str:
        """Build the tone description."""
        if tone_override:
            return tone_override
        
        # Infer from industry
        industry = bc.get('industry', '').lower()
        
        tone_map = {
            'hvac': 'Blue-collar honest. Say it like a neighbor would. No corporate polish.',
            'plumbing': 'Direct and practical. No jargon. Like a trusted handyman explaining things.',
            'insurance': 'Warm but knowledgeable. Simplify complex topics. Never condescending.',
            'legal': 'Authoritative but approachable. Professional without being stiff.',
            'restaurant': 'Warm, inviting, personal. Like the owner greeting you at the door.',
            'salon': 'Friendly, confident, trend-aware. Like your favorite stylist chatting.',
            'construction': 'Straightforward, proud of craft. Show the work, skip the fluff.',
            'musician': 'Authentic, raw, personal. Like talking to fans after a show.',
            'saas': 'Smart, concise, slightly irreverent. Engineer-to-engineer respect.',
            'startup': 'Direct, no buzzwords, slightly irreverent. Builder talking to builders.',
            'ai': 'Technical but accessible. Show depth without showing off.',
        }
        
        for keyword, tone in tone_map.items():
            if keyword in industry:
                return tone
        
        return 'Professional but human. Clear and direct. No corporate-speak.'
    
    def _build_differentiator(self, bc: Dict) -> str:
        """Build the unique truth."""
        usp = bc.get('unique_selling_proposition', '')
        if usp:
            return usp
        
        desc = bc.get('business_description', '')
        if desc and len(desc) > 50:
            # Extract something unique from the description
            sentences = desc.split('.')
            if len(sentences) > 1:
                return sentences[1].strip() + '.'
        
        return 'We do the work and let the results speak.'
    
    def _build_proof_points(self, bc: Dict, merag: Dict, instructions: str) -> str:
        """Build specific numbers, awards, metrics."""
        points = []
        
        # From business context
        if bc.get('years_in_business'):
            points.append(f"{bc['years_in_business']} years in business")
        if bc.get('google_rating'):
            points.append(f"{bc['google_rating']} stars on Google")
        if bc.get('total_jobs') or bc.get('total_customers'):
            count = bc.get('total_jobs') or bc.get('total_customers')
            points.append(f"{count:,}+ jobs completed")
        
        # From MERAG
        if merag.get('metrics'):
            metrics = merag['metrics']
            if metrics.get('google_reviews_count'):
                points.append(f"{metrics['google_reviews_count']} Google reviews")
        
        # From instructions (extract awards, milestones)
        if instructions:
            lower = instructions.lower()
            if 'award' in lower or 'won' in lower or 'best' in lower:
                # Include the award mention as a proof point
                points.append(f"Award: {instructions[:100]}")
        
        return ', '.join(points) if points else ''
    
    def _build_people(self, bc: Dict, instructions: str, merag: Dict) -> str:
        """Build named team members with one detail each."""
        people = []
        
        # From business context
        if bc.get('team_members'):
            for member in bc['team_members'][:5]:
                name = member.get('name', '')
                role = member.get('role', '')
                detail = member.get('detail', '')
                if name:
                    entry = name
                    if role:
                        entry += f" ({role})"
                    if detail:
                        entry += f" — {detail}"
                    people.append(entry)
        
        # From instructions (extract mentioned names)
        if instructions and not people:
            # Simple name extraction from instructions
            import re
            # Look for patterns like "hired Marcus", "welcome Tina", "[Name] joined"
            name_patterns = re.findall(
                r'(?:hired|welcome|introducing|new hire|joined|anniversary)\s+([A-Z][a-z]+)',
                instructions
            )
            for name in name_patterns:
                people.append(f"{name} (mentioned in instructions)")
        
        return '; '.join(people) if people else ''
    
    def build_slim_summary(self, bc: Dict) -> str:
        """
        Build a slim 3-4 sentence business summary for Stage 1.
        Less detailed than the full voice brief — just enough for topic selection.
        """
        parts = []
        name = bc.get('business_name', 'Business')
        industry = bc.get('industry', '')
        location = bc.get('location', '')
        audience = bc.get('target_audience', '')
        usp = bc.get('unique_selling_proposition', '')
        desc = bc.get('business_description', '')
        
        if name and industry:
            line = f"{name} is a {industry} business"
            if location:
                line += f" in {location}"
            parts.append(line + ".")
        
        if desc:
            first_sentence = desc.split('.')[0] + '.' if '.' in desc else desc[:200]
            parts.append(first_sentence)
        
        if audience:
            parts.append(f"Target audience: {audience}.")
        
        if usp:
            parts.append(f"Key differentiator: {usp}.")
        
        return ' '.join(parts) if parts else f"{name} business."

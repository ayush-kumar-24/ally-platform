from typing import Any, Optional
import datetime
import decimal
import uuid

from sqlalchemy import Boolean, CHAR, CheckConstraint, Column, Computed, Date, DateTime, ForeignKeyConstraint, Index, Integer, Numeric, PrimaryKeyConstraint, Sequence, SmallInteger, String, Table, Text, UniqueConstraint, Uuid, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.session import Base
from pgvector.sqlalchemy import Vector



class AgentInterpretations(Base):
    __tablename__ = 'agent_interpretations'
    __table_args__ = (
        PrimaryKeyConstraint('interpretation_id', name='agent_interpretations_pkey'),
        Index('idx_agent_interpretations_embedding', 'embedding', postgresql_ops={'embedding': 'vector_cosine_ops'}, postgresql_using='hnsw', postgresql_where='(embedding IS NOT NULL)'),
    )

    interpretation_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    category: Mapped[str] = mapped_column(String(100), nullable=False)
    founder_statement: Mapped[str] = mapped_column(Text, nullable=False)
    surface_risk: Mapped[str] = mapped_column(Text, nullable=False)
    probe_question: Mapped[str] = mapped_column(Text, nullable=False)
    likely_root_cause: Mapped[str] = mapped_column(Text, nullable=False)
    linked_root_cause_ids: Mapped[Optional[dict]] = mapped_column(JSONB, server_default=text("'[]'::jsonb"))
    linked_problem_ids: Mapped[Optional[dict]] = mapped_column(JSONB, server_default=text("'[]'::jsonb"))
    embedding: Mapped[Optional[Any]] = mapped_column(Vector(384))
    created_at: Mapped[Optional[datetime.datetime]] = mapped_column(DateTime(True), server_default=text('now()'))
    updated_at: Mapped[Optional[datetime.datetime]] = mapped_column(DateTime(True), server_default=text('now()'))


class Archetypes(Base):
    __tablename__ = 'archetypes'
    __table_args__ = (
        PrimaryKeyConstraint('archetype_id', name='archetypes_pkey'),
        UniqueConstraint('archetype_code', name='archetypes_archetype_code_key'),
        Index('idx_archetypes_embedding', 'embedding', postgresql_ops={'embedding': 'vector_cosine_ops'}, postgresql_using='hnsw'),
    )

    archetype_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    archetype_code: Mapped[str] = mapped_column(String(20), nullable=False)
    archetype_name: Mapped[str] = mapped_column(String(100), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    key_traits: Mapped[dict] = mapped_column(JSONB, nullable=False, server_default=text("'[]'::jsonb"))
    created_at: Mapped[datetime.datetime] = mapped_column(DateTime(True), nullable=False, server_default=text('now()'))
    updated_at: Mapped[datetime.datetime] = mapped_column(DateTime(True), nullable=False, server_default=text('now()'))
    assignment_criteria: Mapped[Optional[str]] = mapped_column(Text)
    linked_founder_dimension_ids: Mapped[Optional[dict]] = mapped_column(JSONB, server_default=text("'[]'::jsonb"))
    embedding: Mapped[Optional[Any]] = mapped_column(Vector(384))


class BehaviourPatterns(Base):
    __tablename__ = 'behaviour_patterns'
    __table_args__ = (
        CheckConstraint("pattern_type::text = ANY (ARRAY['communication_style'::character varying, 'stress_response'::character varying, 'burnout_stage'::character varying, 'language_signal'::character varying]::text[])", name='behaviour_patterns_pattern_type_check'),
        PrimaryKeyConstraint('pattern_id', name='behaviour_patterns_pkey'),
        Index('idx_behaviour_patterns_embedding', 'embedding', postgresql_ops={'embedding': 'vector_cosine_ops'}, postgresql_using='hnsw', postgresql_where='(embedding IS NOT NULL)'),
    )

    pattern_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    pattern_name: Mapped[str] = mapped_column(String(100), nullable=False)
    pattern_type: Mapped[str] = mapped_column(String(50), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    observable_signals: Mapped[dict] = mapped_column(JSONB, nullable=False, server_default=text("'[]'::jsonb"))
    language_cues: Mapped[dict] = mapped_column(JSONB, nullable=False, server_default=text("'[]'::jsonb"))
    what_they_say: Mapped[Optional[str]] = mapped_column(Text)
    what_they_mean: Mapped[Optional[str]] = mapped_column(Text)
    empathy_response: Mapped[Optional[str]] = mapped_column(Text)
    linked_root_cause_ids: Mapped[Optional[dict]] = mapped_column(JSONB, server_default=text("'[]'::jsonb"))
    embedding: Mapped[Optional[Any]] = mapped_column(Vector(384))
    created_at: Mapped[Optional[datetime.datetime]] = mapped_column(DateTime(True), server_default=text('now()'))
    updated_at: Mapped[Optional[datetime.datetime]] = mapped_column(DateTime(True), server_default=text('now()'))


class BlindSpots(Base):
    __tablename__ = 'blind_spots'
    __table_args__ = (
        CheckConstraint("blind_spot_type::text = ANY (ARRAY['external_to_internal'::character varying, 'internal_to_external'::character varying]::text[])", name='blind_spots_blind_spot_type_check'),
        PrimaryKeyConstraint('blind_spot_id', name='blind_spots_pkey'),
    )

    blind_spot_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    blind_spot_name: Mapped[str] = mapped_column(String(200), nullable=False)
    blind_spot_type: Mapped[str] = mapped_column(String(50), nullable=False)
    what_founder_says: Mapped[str] = mapped_column(Text, nullable=False)
    what_founder_thinks: Mapped[str] = mapped_column(Text, nullable=False)
    what_it_actually_is: Mapped[str] = mapped_column(Text, nullable=False)
    probe_questions: Mapped[dict] = mapped_column(JSONB, nullable=False, server_default=text("'[]'::jsonb"))
    linked_problem_ids: Mapped[Optional[dict]] = mapped_column(JSONB, server_default=text("'[]'::jsonb"))
    linked_root_cause_ids: Mapped[Optional[dict]] = mapped_column(JSONB, server_default=text("'[]'::jsonb"))
    created_at: Mapped[Optional[datetime.datetime]] = mapped_column(DateTime(True), server_default=text('now()'))
    updated_at: Mapped[Optional[datetime.datetime]] = mapped_column(DateTime(True), server_default=text('now()'))


class BusinessDimensions(Base):
    __tablename__ = 'business_dimensions'
    __table_args__ = (
        PrimaryKeyConstraint('dimension_id', name='business_dimensions_pkey'),
        UniqueConstraint('dimension_code', name='business_dimensions_dimension_code_key'),
    )

    dimension_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    dimension_code: Mapped[str] = mapped_column(String(20), nullable=False)
    dimension_name: Mapped[str] = mapped_column(String(100), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    scoring_rubric: Mapped[dict] = mapped_column(JSONB, nullable=False, server_default=text("'{}'::jsonb"))
    display_order: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text('0'))
    created_at: Mapped[datetime.datetime] = mapped_column(DateTime(True), nullable=False, server_default=text('now()'))
    updated_at: Mapped[datetime.datetime] = mapped_column(DateTime(True), nullable=False, server_default=text('now()'))


class FounderDimensions(Base):
    __tablename__ = 'founder_dimensions'
    __table_args__ = (
        CheckConstraint("dimension_type::text = ANY (ARRAY['categorical'::character varying, 'narrative'::character varying, 'behavioral_inferred'::character varying]::text[])", name='founder_dimensions_dimension_type_check'),
        PrimaryKeyConstraint('dimension_id', name='founder_dimensions_pkey'),
        UniqueConstraint('dimension_code', name='founder_dimensions_dimension_code_key'),
    )

    dimension_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    dimension_code: Mapped[str] = mapped_column(String(20), nullable=False)
    dimension_name: Mapped[str] = mapped_column(String(100), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    scoring_rubric: Mapped[dict] = mapped_column(JSONB, nullable=False, server_default=text("'{}'::jsonb"))
    display_order: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text('0'))
    created_at: Mapped[datetime.datetime] = mapped_column(DateTime(True), nullable=False, server_default=text('now()'))
    updated_at: Mapped[datetime.datetime] = mapped_column(DateTime(True), nullable=False, server_default=text('now()'))
    dimension_type: Mapped[Optional[str]] = mapped_column(String(20))
    why_it_matters: Mapped[Optional[str]] = mapped_column(Text)

    visual_question_bank: Mapped[list['VisualQuestionBank']] = relationship('VisualQuestionBank', back_populates='primary_dimension')
    founder_dimension_profile: Mapped[list['FounderDimensionProfile']] = relationship('FounderDimensionProfile', back_populates='dimension')


class FounderStages(Base):
    __tablename__ = 'founder_stages'
    __table_args__ = (
        PrimaryKeyConstraint('stage_id', name='founder_stages_pkey'),
    )

    stage_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    stage_name: Mapped[str] = mapped_column(String(100), nullable=False)
    stage_order: Mapped[int] = mapped_column(Integer, nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    key_characteristics: Mapped[dict] = mapped_column(JSONB, nullable=False, server_default=text("'[]'::jsonb"))
    min_criteria: Mapped[dict] = mapped_column(JSONB, nullable=False, server_default=text("'{}'::jsonb"))
    max_criteria: Mapped[dict] = mapped_column(JSONB, nullable=False, server_default=text("'{}'::jsonb"))
    top_operational_problems: Mapped[dict] = mapped_column(JSONB, nullable=False, server_default=text("'[]'::jsonb"))
    top_psychological_challenges: Mapped[dict] = mapped_column(JSONB, nullable=False, server_default=text("'[]'::jsonb"))
    criteria_version: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text('1'))
    onboarding_label: Mapped[Optional[str]] = mapped_column(String(100))
    created_at: Mapped[Optional[datetime.datetime]] = mapped_column(DateTime(True), server_default=text('now()'))
    updated_at: Mapped[Optional[datetime.datetime]] = mapped_column(DateTime(True), server_default=text('now()'))

    founders: Mapped[list['Founders']] = relationship('Founders', back_populates='stage')
    industry_stage_thresholds: Mapped[list['IndustryStageThresholds']] = relationship('IndustryStageThresholds', back_populates='stage')
    problem_stage_mapping: Mapped[list['ProblemStageMapping']] = relationship('ProblemStageMapping', back_populates='stage')
    root_cause_weights: Mapped[list['RootCauseWeights']] = relationship('RootCauseWeights', back_populates='stage')
    sessions: Mapped[list['Sessions']] = relationship('Sessions', back_populates='founder_stage')
    stage_assessments: Mapped[list['StageAssessments']] = relationship('StageAssessments', back_populates='stage')


class Frameworks(Base):
    __tablename__ = 'frameworks'
    __table_args__ = (
        PrimaryKeyConstraint('framework_id', name='frameworks_pkey'),
        UniqueConstraint('framework_code', name='frameworks_framework_code_key'),
        Index('idx_frameworks_category', 'category'),
    )

    framework_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    framework_code: Mapped[str] = mapped_column(String(30), nullable=False)
    framework_name: Mapped[str] = mapped_column(String(200), nullable=False)
    category: Mapped[str] = mapped_column(String(100), nullable=False)
    what_it_is: Mapped[str] = mapped_column(Text, nullable=False)
    problem_it_solves: Mapped[str] = mapped_column(Text, nullable=False)
    stage_relevance: Mapped[dict] = mapped_column(JSONB, nullable=False, server_default=text("'[]'::jsonb"))
    industry_relevance: Mapped[dict] = mapped_column(JSONB, nullable=False, server_default=text("'[]'::jsonb"))
    how_alley_uses_it: Mapped[str] = mapped_column(Text, nullable=False)
    linked_root_cause_ids: Mapped[dict] = mapped_column(JSONB, nullable=False, server_default=text("'[]'::jsonb"))
    creator: Mapped[Optional[str]] = mapped_column(String(200))
    linked_intervention_ids: Mapped[Optional[dict]] = mapped_column(JSONB, server_default=text("'[]'::jsonb"))
    source_reference: Mapped[Optional[str]] = mapped_column(String(300))
    created_at: Mapped[Optional[datetime.datetime]] = mapped_column(DateTime(True), server_default=text('now()'))
    updated_at: Mapped[Optional[datetime.datetime]] = mapped_column(DateTime(True), server_default=text('now()'))


class Industries(Base):
    __tablename__ = 'industries'
    __table_args__ = (
        PrimaryKeyConstraint('industry_id', name='industries_pkey'),
        UniqueConstraint('industry_code', name='industries_industry_code_key'),
    )

    industry_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    industry_code: Mapped[str] = mapped_column(String(20), nullable=False)
    industry_name: Mapped[str] = mapped_column(String(100), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    defining_characteristics: Mapped[dict] = mapped_column(JSONB, nullable=False, server_default=text("'[]'::jsonb"))
    top_pain_point_weights: Mapped[dict] = mapped_column(JSONB, nullable=False, server_default=text("'{}'::jsonb"))
    key_metrics: Mapped[dict] = mapped_column(JSONB, nullable=False, server_default=text("'{}'::jsonb"))
    red_flags: Mapped[dict] = mapped_column(JSONB, nullable=False, server_default=text("'[]'::jsonb"))
    empathy_language: Mapped[dict] = mapped_column(JSONB, nullable=False, server_default=text("'{}'::jsonb"))
    recommended_benchmarks: Mapped[dict] = mapped_column(JSONB, nullable=False, server_default=text("'{}'::jsonb"))
    created_at: Mapped[Optional[datetime.datetime]] = mapped_column(DateTime(True), server_default=text('now()'))
    updated_at: Mapped[Optional[datetime.datetime]] = mapped_column(DateTime(True), server_default=text('now()'))
    industry_subtitle: Mapped[Optional[str]] = mapped_column(String(200))
    why_industry_context_matters: Mapped[Optional[str]] = mapped_column(Text)
    top_pain_points: Mapped[Optional[dict]] = mapped_column(JSONB, server_default=text("'[]'::jsonb"))
    diagnostic_adjustments: Mapped[Optional[dict]] = mapped_column(JSONB, server_default=text("'{}'::jsonb"))
    red_flags_description: Mapped[Optional[str]] = mapped_column(Text)
    stage_thresholds_inr: Mapped[Optional[dict]] = mapped_column(JSONB, server_default=text("'{}'::jsonb"))

    founders: Mapped[list['Founders']] = relationship('Founders', back_populates='industry_mapped')
    industry_stage_thresholds: Mapped[list['IndustryStageThresholds']] = relationship('IndustryStageThresholds', back_populates='industry')
    sessions: Mapped[list['Sessions']] = relationship('Sessions', back_populates='founder_industry')


class PromptLibrary(Base):
    __tablename__ = 'prompt_library'
    __table_args__ = (
        CheckConstraint("category::text = ANY (ARRAY['diagnosis'::character varying, 'report'::character varying, 'chat'::character varying, 'distress'::character varying, 'recommendation'::character varying, 'planning'::character varying, 'other'::character varying]::text[])", name='prompt_library_category_check'),
        PrimaryKeyConstraint('prompt_id', name='prompt_library_pkey'),
        UniqueConstraint('prompt_code', name='prompt_library_prompt_code_key'),
        Index('idx_prompt_library_category', 'category', postgresql_where='(is_active = true)'),
    )

    prompt_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    prompt_code: Mapped[str] = mapped_column(String(50), nullable=False)
    prompt_name: Mapped[str] = mapped_column(String(150), nullable=False)
    category: Mapped[str] = mapped_column(String(30), nullable=False)
    purpose: Mapped[str] = mapped_column(Text, nullable=False)
    prompt_text: Mapped[str] = mapped_column(Text, nullable=False)
    version: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text('1'))
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text('true'))
    created_at: Mapped[datetime.datetime] = mapped_column(DateTime(True), nullable=False, server_default=text('now()'))
    updated_at: Mapped[datetime.datetime] = mapped_column(DateTime(True), nullable=False, server_default=text('now()'))


class QuestionTags(Base):
    __tablename__ = 'question_tags'
    __table_args__ = (
        PrimaryKeyConstraint('tag_id', name='question_tags_pkey'),
        UniqueConstraint('tag_name', name='question_tags_tag_name_key'),
    )

    tag_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    tag_name: Mapped[str] = mapped_column(String(100), nullable=False)
    tag_description: Mapped[Optional[str]] = mapped_column(Text)
    created_at: Mapped[Optional[datetime.datetime]] = mapped_column(DateTime(True), server_default=text('now()'))

    question_tag_mapping: Mapped[list['QuestionTagMapping']] = relationship('QuestionTagMapping', back_populates='tag')


class RagDocuments(Base):
    __tablename__ = 'rag_documents'
    __table_args__ = (
        CheckConstraint("document_type::text = ANY (ARRAY['client_report'::character varying, 'case_study'::character varying, 'consultant_note'::character varying, 'playbook'::character varying]::text[])", name='rag_documents_document_type_check'),
        CheckConstraint("review_status::text = ANY (ARRAY['pending'::character varying, 'approved'::character varying, 'rejected'::character varying]::text[])", name='rag_documents_review_status_check'),
        PrimaryKeyConstraint('document_id', name='rag_documents_pkey'),
    )

    document_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    document_name: Mapped[str] = mapped_column(String(300), nullable=False)
    document_type: Mapped[str] = mapped_column(String(50), nullable=False)
    review_status: Mapped[str] = mapped_column(String(30), nullable=False, server_default=text("'pending'::character varying"))
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text('true'))
    source_label: Mapped[Optional[str]] = mapped_column(String(200))
    content_summary: Mapped[Optional[str]] = mapped_column(Text)
    industry_tag: Mapped[Optional[str]] = mapped_column(String(100))
    stage_relevance: Mapped[Optional[str]] = mapped_column(String(50))
    reviewed_by: Mapped[Optional[str]] = mapped_column(String(100))
    created_at: Mapped[Optional[datetime.datetime]] = mapped_column(DateTime(True), server_default=text('now()'))
    updated_at: Mapped[Optional[datetime.datetime]] = mapped_column(DateTime(True), server_default=text('now()'))

    rag_chunks: Mapped[list['RagChunks']] = relationship('RagChunks', back_populates='document')


class ReadinessPillars(Base):
    __tablename__ = 'readiness_pillars'
    __table_args__ = (
        PrimaryKeyConstraint('pillar_id', name='readiness_pillars_pkey'),
    )

    pillar_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    pillar_name: Mapped[str] = mapped_column(String(100), nullable=False)
    pillar_description: Mapped[str] = mapped_column(Text, nullable=False)
    pillar_weightage: Mapped[decimal.Decimal] = mapped_column(Numeric(5, 2), nullable=False)
    pillar_order: Mapped[int] = mapped_column(Integer, nullable=False)
    created_at: Mapped[Optional[datetime.datetime]] = mapped_column(DateTime(True), server_default=text('now()'))
    updated_at: Mapped[Optional[datetime.datetime]] = mapped_column(DateTime(True), server_default=text('now()'))
    what_falls_under: Mapped[Optional[dict]] = mapped_column(JSONB, server_default=text("'[]'::jsonb"))
    score_bands: Mapped[Optional[dict]] = mapped_column(JSONB, server_default=text("'[]'::jsonb"))
    stage_behaviour: Mapped[Optional[dict]] = mapped_column(JSONB, server_default=text("'[]'::jsonb"))
    red_flag_threshold: Mapped[Optional[decimal.Decimal]] = mapped_column(Numeric(5, 2))
    red_flag_note: Mapped[Optional[str]] = mapped_column(Text)

    problems: Mapped[list['Problems']] = relationship('Problems', back_populates='pillar')


class ScoringRules(Base):
    __tablename__ = 'scoring_rules'
    __table_args__ = (
        PrimaryKeyConstraint('rule_id', name='scoring_rules_pkey'),
        UniqueConstraint('rule_code', name='scoring_rules_rule_code_key'),
    )

    rule_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    rule_code: Mapped[str] = mapped_column(String(50), nullable=False)
    rule_name: Mapped[str] = mapped_column(String(200), nullable=False)
    rule_value: Mapped[decimal.Decimal] = mapped_column(Numeric(8, 4), nullable=False)
    rule_description: Mapped[str] = mapped_column(Text, nullable=False)
    source_document: Mapped[str] = mapped_column(String(50), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text('true'))
    created_at: Mapped[Optional[datetime.datetime]] = mapped_column(DateTime(True), server_default=text('now()'))
    updated_at: Mapped[Optional[datetime.datetime]] = mapped_column(DateTime(True), server_default=text('now()'))


class StageDiagnosisLogic(Base):
    __tablename__ = 'stage_diagnosis_logic'
    __table_args__ = (
        CheckConstraint("stage_group::text = ANY (ARRAY['Stage 0'::character varying, 'Stage 0→1'::character varying, 'Stage 1→10+'::character varying]::text[])", name='stage_diagnosis_logic_stage_group_check'),
        PrimaryKeyConstraint('logic_id', name='stage_diagnosis_logic_pkey'),
        Index('idx_stage_diagnosis_logic_group', 'stage_group'),
    )

    logic_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    stage_group: Mapped[str] = mapped_column(String(20), nullable=False)
    common_symptom: Mapped[str] = mapped_column(Text, nullable=False)
    what_it_actually_hides: Mapped[str] = mapped_column(Text, nullable=False)
    linked_root_cause_ids: Mapped[dict] = mapped_column(JSONB, nullable=False, server_default=text("'[]'::jsonb"))
    display_order: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text('0'))
    created_at: Mapped[datetime.datetime] = mapped_column(DateTime(True), nullable=False, server_default=text('now()'))
    updated_at: Mapped[datetime.datetime] = mapped_column(DateTime(True), nullable=False, server_default=text('now()'))
    tone_guidance: Mapped[Optional[str]] = mapped_column(Text)


class Founders(Base):
    __tablename__ = 'founders'
    __table_args__ = (
        CheckConstraint("business_model::text = ANY (ARRAY['B2B'::character varying, 'B2C'::character varying, 'B2B2C'::character varying, 'marketplace'::character varying, 'D2C'::character varying, 'other'::character varying]::text[])", name='founders_business_model_check'),
        CheckConstraint("current_revenue::text = ANY (ARRAY['pre_revenue'::character varying, 'under_1L'::character varying, '1L_5L'::character varying, '5L_25L'::character varying, '25L_1Cr'::character varying, 'above_1Cr'::character varying]::text[])", name='founders_current_revenue_check'),
        CheckConstraint("emotional_state::text = ANY (ARRAY['excited'::character varying, 'inspired'::character varying, 'confident'::character varying, 'curious'::character varying, 'overwhelmed'::character varying, 'stuck'::character varying, 'determined'::character varying, 'hopeful'::character varying]::text[])", name='founders_emotional_state_check'),
        CheckConstraint("experience_level::text = ANY (ARRAY['first_time'::character varying, 'one_company'::character varying, 'serial'::character varying, 'investor'::character varying, 'mentor'::character varying, 'executive'::character varying]::text[])", name='founders_experience_level_check'),
        CheckConstraint("plan_type::text = ANY (ARRAY['free'::character varying, 'starter'::character varying, 'pro'::character varying, 'enterprise'::character varying]::text[])", name='founders_plan_type_check'),
        CheckConstraint("team_size::text = ANY (ARRAY['solo'::character varying, '2_5'::character varying, '6_10'::character varying, '11_25'::character varying, '26_50'::character varying, '50_plus'::character varying]::text[])", name='founders_team_size_check'),
        CheckConstraint("working_relationship::text = ANY (ARRAY['coach'::character varying, 'cofounder'::character varying, 'strategist'::character varying, 'accountability'::character varying, 'brainstorm'::character varying, 'research'::character varying]::text[])", name='founders_working_relationship_check'),
        ForeignKeyConstraint(['industry_mapped_id'], ['industries.industry_id'], name='founders_industry_mapped_id_fkey'),
        ForeignKeyConstraint(['stage_id'], ['founder_stages.stage_id'], name='founders_stage_id_fkey'),
        PrimaryKeyConstraint('founder_id', name='founders_pkey'),
        UniqueConstraint('email', name='founders_email_key'),
        UniqueConstraint('user_id', name='founders_user_id_key'),
        Index('idx_founders_email', 'email'),
        Index('idx_founders_industry', 'industry'),
        Index('idx_founders_stage_id', 'stage_id'),
        Index('idx_founders_user_id', 'user_id'),
    )

    founder_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[uuid.UUID] = mapped_column(Uuid, nullable=False)
    full_name: Mapped[str] = mapped_column(String(200), nullable=False)
    email: Mapped[str] = mapped_column(String(200), nullable=False)
    plan_type: Mapped[str] = mapped_column(String(20), nullable=False, server_default=text("'free'::character varying"))
    diagnosis_used: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text('false'))
    profile_completed: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text('false'))
    onboarding_version: Mapped[str] = mapped_column(String(20), nullable=False, server_default=text("'v2.1-final'::character varying"))
    diagnosis_locked_at: Mapped[Optional[datetime.datetime]] = mapped_column(DateTime(True))
    onboarding_completed_at: Mapped[Optional[datetime.datetime]] = mapped_column(DateTime(True))
    consent_version: Mapped[Optional[str]] = mapped_column(String(20))
    data_retention_expires_at: Mapped[Optional[datetime.datetime]] = mapped_column(DateTime(True))
    deletion_requested_at: Mapped[Optional[datetime.datetime]] = mapped_column(DateTime(True))
    deletion_scheduled_at: Mapped[Optional[datetime.datetime]] = mapped_column(DateTime(True))
    founder_motivation: Mapped[Optional[str]] = mapped_column(Text)
    working_relationship: Mapped[Optional[str]] = mapped_column(String(30))
    support_preferences: Mapped[Optional[dict]] = mapped_column(JSONB, server_default=text("'[]'::jsonb"))
    experience_level: Mapped[Optional[str]] = mapped_column(String(20))
    emotional_state: Mapped[Optional[str]] = mapped_column(String(20))
    adaptive_reflection: Mapped[Optional[str]] = mapped_column(Text)
    adaptive_question_id: Mapped[Optional[str]] = mapped_column(String(20))
    decision_making_style: Mapped[Optional[str]] = mapped_column(String(30))
    building_summary: Mapped[Optional[str]] = mapped_column(Text)
    problem_statement: Mapped[Optional[str]] = mapped_column(Text)
    customer_segment: Mapped[Optional[str]] = mapped_column(String(30))
    customer_segment_other: Mapped[Optional[str]] = mapped_column(String(200))
    industry: Mapped[Optional[str]] = mapped_column(String(30))
    industry_mapped_id: Mapped[Optional[int]] = mapped_column(Integer)
    current_challenges: Mapped[Optional[dict]] = mapped_column(JSONB, server_default=text("'[]'::jsonb"))
    goal_90_day: Mapped[Optional[str]] = mapped_column(Text)
    vision_1_year: Mapped[Optional[str]] = mapped_column(Text)
    team_size: Mapped[Optional[str]] = mapped_column(String(20))
    current_revenue: Mapped[Optional[str]] = mapped_column(String(30))
    business_model: Mapped[Optional[str]] = mapped_column(String(30))
    website: Mapped[Optional[str]] = mapped_column(String(300))
    linkedin_url: Mapped[Optional[str]] = mapped_column(String(300))
    social_profiles: Mapped[Optional[dict]] = mapped_column(JSONB, server_default=text("'{}'::jsonb"))
    preferred_language: Mapped[Optional[str]] = mapped_column(String(10), server_default=text("'en'::character varying"))
    notification_preferences: Mapped[Optional[dict]] = mapped_column(JSONB, server_default=text('\'{"in_app_all": true, "email_reminders": true, "email_report_ready": true}\'::jsonb'))
    created_at: Mapped[Optional[datetime.datetime]] = mapped_column(DateTime(True), server_default=text('now()'))
    updated_at: Mapped[Optional[datetime.datetime]] = mapped_column(DateTime(True), server_default=text('now()'))
    tour_seen_at: Mapped[Optional[datetime.datetime]] = mapped_column(DateTime(True))
    stage_id: Mapped[Optional[int]] = mapped_column(Integer)

    industry_mapped: Mapped[Optional['Industries']] = relationship('Industries', back_populates='founders')
    stage: Mapped[Optional['FounderStages']] = relationship('FounderStages', back_populates='founders')
    consent_history: Mapped[list['ConsentHistory']] = relationship('ConsentHistory', back_populates='founder')
    consents: Mapped['Consents'] = relationship('Consents', uselist=False, back_populates='founder')
    conversations: Mapped[list['Conversations']] = relationship('Conversations', back_populates='founder')
    cookie_preferences: Mapped[list['CookiePreferences']] = relationship('CookiePreferences', back_populates='founder')
    data_deletion_requests: Mapped['DataDeletionRequests'] = relationship('DataDeletionRequests', uselist=False, back_populates='founder')
    discovery_calls: Mapped[list['DiscoveryCalls']] = relationship('DiscoveryCalls', back_populates='founder')
    founder_context: Mapped['FounderContext'] = relationship('FounderContext', uselist=False, back_populates='founder')
    founder_dimension_profile: Mapped[list['FounderDimensionProfile']] = relationship('FounderDimensionProfile', back_populates='founder')
    founder_visual_choices: Mapped[list['FounderVisualChoices']] = relationship('FounderVisualChoices', back_populates='founder')
    notifications: Mapped[list['Notifications']] = relationship('Notifications', back_populates='founder')
    privacy_requests: Mapped[list['PrivacyRequests']] = relationship('PrivacyRequests', back_populates='founder')
    report_shares: Mapped[list['ReportShares']] = relationship('ReportShares', back_populates='founder')
    subscriptions: Mapped[list['Subscriptions']] = relationship('Subscriptions', back_populates='founder')
    user_token_usage: Mapped[list['UserTokenUsage']] = relationship('UserTokenUsage', back_populates='founder')
    webhook_logs: Mapped[list['WebhookLogs']] = relationship('WebhookLogs', back_populates='founder')
    admin_notes: Mapped[list['AdminNotes']] = relationship('AdminNotes', back_populates='founder')
    daily_actions: Mapped[list['DailyActions']] = relationship('DailyActions', back_populates='founder')
    file_uploads: Mapped[list['FileUploads']] = relationship('FileUploads', back_populates='founder')
    payments: Mapped[list['Payments']] = relationship('Payments', back_populates='founder')
    sessions: Mapped[list['Sessions']] = relationship('Sessions', back_populates='founder')
    answers: Mapped[list['Answers']] = relationship('Answers', back_populates='founder')
    detected_root_causes: Mapped[list['DetectedRootCauses']] = relationship('DetectedRootCauses', back_populates='founder')
    founder_reports: Mapped[list['FounderReports']] = relationship('FounderReports', back_populates='founder')
    rag_retrieval_log: Mapped[list['RagRetrievalLog']] = relationship('RagRetrievalLog', back_populates='founder')
    stage_assessments: Mapped[list['StageAssessments']] = relationship('StageAssessments', back_populates='founder')
    founder_feedback: Mapped[list['FounderFeedback']] = relationship('FounderFeedback', back_populates='founder')
    internal_intelligence_reports: Mapped[list['InternalIntelligenceReports']] = relationship('InternalIntelligenceReports', back_populates='founder')


class IndustryStageThresholds(Base):
    __tablename__ = 'industry_stage_thresholds'
    __table_args__ = (
        ForeignKeyConstraint(['industry_id'], ['industries.industry_id'], name='industry_stage_thresholds_industry_id_fkey'),
        ForeignKeyConstraint(['stage_id'], ['founder_stages.stage_id'], name='industry_stage_thresholds_stage_id_fkey'),
        PrimaryKeyConstraint('threshold_id', name='industry_stage_thresholds_pkey'),
        UniqueConstraint('industry_id', 'stage_id', name='industry_stage_thresholds_industry_id_stage_id_key'),
    )

    threshold_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    industry_id: Mapped[int] = mapped_column(Integer, nullable=False)
    stage_id: Mapped[int] = mapped_column(Integer, nullable=False)
    stage_entry_criteria: Mapped[dict] = mapped_column(JSONB, nullable=False, server_default=text("'{}'::jsonb"))
    stage_exit_criteria: Mapped[dict] = mapped_column(JSONB, nullable=False, server_default=text("'{}'::jsonb"))
    notes: Mapped[Optional[str]] = mapped_column(Text)

    industry: Mapped['Industries'] = relationship('Industries', back_populates='industry_stage_thresholds')
    stage: Mapped['FounderStages'] = relationship('FounderStages', back_populates='industry_stage_thresholds')


class Problems(Base):
    __tablename__ = 'problems'
    __table_args__ = (
        CheckConstraint("layer::text = ANY (ARRAY['external'::character varying, 'internal'::character varying]::text[])", name='problems_layer_check'),
        CheckConstraint('severity_max >= 1 AND severity_max <= 10', name='problems_severity_max_check'),
        CheckConstraint('severity_min >= 1 AND severity_min <= 10', name='problems_severity_min_check'),
        ForeignKeyConstraint(['pillar_id'], ['readiness_pillars.pillar_id'], name='problems_pillar_id_fkey'),
        PrimaryKeyConstraint('problem_id', name='problems_pkey'),
        UniqueConstraint('problem_code', name='problems_problem_code_key'),
        Index('idx_problems_category', 'category'),
        Index('idx_problems_code', 'problem_code'),
        Index('idx_problems_embedding', 'embedding', postgresql_ops={'embedding': 'vector_cosine_ops'}, postgresql_using='hnsw', postgresql_where='(embedding IS NOT NULL)'),
        Index('idx_problems_pillar', 'pillar_id'),
    )

    problem_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    problem_code: Mapped[str] = mapped_column(String(20), nullable=False)
    problem_name: Mapped[str] = mapped_column(String(200), nullable=False)
    category: Mapped[str] = mapped_column(String(100), nullable=False)
    layer: Mapped[str] = mapped_column(String(20), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    severity_min: Mapped[int] = mapped_column(Integer, nullable=False)
    severity_max: Mapped[int] = mapped_column(Integer, nullable=False)
    symptoms: Mapped[dict] = mapped_column(JSONB, nullable=False, server_default=text("'[]'::jsonb"))
    pillar_id: Mapped[int] = mapped_column(Integer, nullable=False)
    subcategory: Mapped[Optional[str]] = mapped_column(String(100))
    related_problem_ids: Mapped[Optional[dict]] = mapped_column(JSONB, server_default=text("'[]'::jsonb"))
    embedding: Mapped[Optional[Any]] = mapped_column(Vector(384))
    created_at: Mapped[Optional[datetime.datetime]] = mapped_column(DateTime(True), server_default=text('now()'))
    updated_at: Mapped[Optional[datetime.datetime]] = mapped_column(DateTime(True), server_default=text('now()'))

    pillar: Mapped['ReadinessPillars'] = relationship('ReadinessPillars', back_populates='problems')
    interventions: Mapped[list['Interventions']] = relationship('Interventions', back_populates='problem')
    problem_stage_mapping: Mapped[list['ProblemStageMapping']] = relationship('ProblemStageMapping', back_populates='problem')
    root_causes: Mapped[list['RootCauses']] = relationship('RootCauses', back_populates='problem')
    questions: Mapped[list['Questions']] = relationship('Questions', back_populates='problem')


class RagChunks(Base):
    __tablename__ = 'rag_chunks'
    __table_args__ = (
        ForeignKeyConstraint(['document_id'], ['rag_documents.document_id'], ondelete='CASCADE', name='rag_chunks_document_id_fkey'),
        PrimaryKeyConstraint('chunk_id', name='rag_chunks_pkey'),
        UniqueConstraint('document_id', 'chunk_index', name='rag_chunks_document_id_chunk_index_key'),
        Index('idx_rag_chunks_embedding', 'embedding', postgresql_ops={'embedding': 'vector_cosine_ops'}, postgresql_using='hnsw'),
    )

    chunk_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    document_id: Mapped[int] = mapped_column(Integer, nullable=False)
    chunk_index: Mapped[int] = mapped_column(Integer, nullable=False)
    chunk_text: Mapped[str] = mapped_column(Text, nullable=False)
    embedding: Mapped[Any] = mapped_column(Vector(384), nullable=False)
    embedding_model: Mapped[str] = mapped_column(String(100), nullable=False, server_default=text("'gte-small'::character varying"))
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text('true'))
    chunk_token_count: Mapped[Optional[int]] = mapped_column(Integer)
    metadata_tags: Mapped[Optional[dict]] = mapped_column(JSONB, server_default=text("'{}'::jsonb"))
    created_at: Mapped[Optional[datetime.datetime]] = mapped_column(DateTime(True), server_default=text('now()'))

    document: Mapped['RagDocuments'] = relationship('RagDocuments', back_populates='rag_chunks')


class VisualQuestionBank(Base):
    __tablename__ = 'visual_question_bank'
    __table_args__ = (
        CheckConstraint("primary_stage_group::text = ANY (ARRAY['Stage 0'::character varying, 'Stage 0→1'::character varying, 'Stage 1→10+'::character varying]::text[])", name='visual_question_bank_primary_stage_group_check'),
        ForeignKeyConstraint(['primary_dimension_id'], ['founder_dimensions.dimension_id'], name='visual_question_bank_primary_dimension_id_fkey'),
        PrimaryKeyConstraint('visual_question_id', name='visual_question_bank_pkey'),
        UniqueConstraint('visual_question_code', name='visual_question_bank_visual_question_code_key'),
    )

    visual_question_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    visual_question_code: Mapped[str] = mapped_column(String(30), nullable=False)
    situation_context: Mapped[str] = mapped_column(Text, nullable=False)
    option_a_label: Mapped[str] = mapped_column(String(150), nullable=False)
    option_a_meaning: Mapped[str] = mapped_column(Text, nullable=False)
    option_b_label: Mapped[str] = mapped_column(String(150), nullable=False)
    option_b_meaning: Mapped[str] = mapped_column(Text, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text('false'))
    created_at: Mapped[datetime.datetime] = mapped_column(DateTime(True), nullable=False, server_default=text('now()'))
    updated_at: Mapped[datetime.datetime] = mapped_column(DateTime(True), nullable=False, server_default=text('now()'))
    option_a_image_url: Mapped[Optional[str]] = mapped_column(Text)
    option_b_image_url: Mapped[Optional[str]] = mapped_column(Text)
    primary_dimension_id: Mapped[Optional[int]] = mapped_column(Integer)
    primary_stage_group: Mapped[Optional[str]] = mapped_column(String(20))

    primary_dimension: Mapped[Optional['FounderDimensions']] = relationship('FounderDimensions', back_populates='visual_question_bank')
    founder_visual_choices: Mapped[list['FounderVisualChoices']] = relationship('FounderVisualChoices', back_populates='visual_question')


class ConsentHistory(Base):
    __tablename__ = 'consent_history'
    __table_args__ = (
        CheckConstraint("action::text = ANY (ARRAY['accepted'::character varying, 'rejected'::character varying, 'withdrawn'::character varying, 'updated'::character varying, 're_consented'::character varying]::text[])", name='consent_history_action_check'),
        ForeignKeyConstraint(['founder_id'], ['founders.founder_id'], name='consent_history_founder_id_fkey'),
        PrimaryKeyConstraint('history_id', name='consent_history_pkey'),
    )

    history_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    founder_id: Mapped[int] = mapped_column(Integer, nullable=False)
    action: Mapped[str] = mapped_column(String(30), nullable=False)
    consent_type: Mapped[str] = mapped_column(String(30), nullable=False)
    new_value: Mapped[bool] = mapped_column(Boolean, nullable=False)
    privacy_policy_version: Mapped[str] = mapped_column(String(20), nullable=False)
    ip_address: Mapped[str] = mapped_column(String(45), nullable=False)
    previous_value: Mapped[Optional[bool]] = mapped_column(Boolean)
    browser: Mapped[Optional[str]] = mapped_column(Text)
    created_at: Mapped[Optional[datetime.datetime]] = mapped_column(DateTime(True), server_default=text('now()'))

    founder: Mapped['Founders'] = relationship('Founders', back_populates='consent_history')


class Consents(Base):
    __tablename__ = 'consents'
    __table_args__ = (
        ForeignKeyConstraint(['founder_id'], ['founders.founder_id'], ondelete='CASCADE', name='consents_founder_id_fkey'),
        PrimaryKeyConstraint('consent_id', name='consents_pkey'),
        UniqueConstraint('founder_id', name='consents_founder_id_key'),
    )

    consent_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    founder_id: Mapped[int] = mapped_column(Integer, nullable=False)
    privacy_policy_version: Mapped[str] = mapped_column(String(20), nullable=False)
    terms_version: Mapped[str] = mapped_column(String(20), nullable=False)
    cookie_consent: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text('false'))
    analytics: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text('false'))
    marketing: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text('false'))
    functional: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text('true'))
    diagnosis_data_consent: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text('false'))
    ip_address: Mapped[str] = mapped_column(String(45), nullable=False)
    consented_at: Mapped[datetime.datetime] = mapped_column(DateTime(True), nullable=False, server_default=text('now()'))
    browser: Mapped[Optional[str]] = mapped_column(Text)
    created_at: Mapped[Optional[datetime.datetime]] = mapped_column(DateTime(True), server_default=text('now()'))

    founder: Mapped['Founders'] = relationship('Founders', back_populates='consents')


class Conversations(Base):
    __tablename__ = 'conversations'
    __table_args__ = (
        CheckConstraint("conversation_type::text = ANY (ARRAY['chat'::character varying, 'diagnosis'::character varying]::text[])", name='conversations_conversation_type_check'),
        CheckConstraint("status::text = ANY (ARRAY['active'::character varying, 'completed'::character varying, 'archived'::character varying]::text[])", name='conversations_status_check'),
        ForeignKeyConstraint(['founder_id'], ['founders.founder_id'], ondelete='CASCADE', name='conversations_founder_id_fkey'),
        PrimaryKeyConstraint('conversation_id', name='conversations_pkey'),
        Index('idx_conversations_founder', 'founder_id'),
        Index('idx_conversations_type', 'conversation_type'),
    )

    conversation_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    founder_id: Mapped[int] = mapped_column(Integer, nullable=False)
    conversation_type: Mapped[str] = mapped_column(String(20), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, server_default=text("'active'::character varying"))
    is_locked: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text('false'))
    message_count: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text('0'))
    title: Mapped[Optional[str]] = mapped_column(String(200))
    locked_at: Mapped[Optional[datetime.datetime]] = mapped_column(DateTime(True))
    lock_reason: Mapped[Optional[str]] = mapped_column(String(100))
    last_message_at: Mapped[Optional[datetime.datetime]] = mapped_column(DateTime(True))
    created_at: Mapped[Optional[datetime.datetime]] = mapped_column(DateTime(True), server_default=text('now()'))
    updated_at: Mapped[Optional[datetime.datetime]] = mapped_column(DateTime(True), server_default=text('now()'))

    founder: Mapped['Founders'] = relationship('Founders', back_populates='conversations')
    file_uploads: Mapped[list['FileUploads']] = relationship('FileUploads', back_populates='conversation')
    rag_retrieval_log: Mapped[list['RagRetrievalLog']] = relationship('RagRetrievalLog', back_populates='conversation')


class CookiePreferences(Base):
    __tablename__ = 'cookie_preferences'
    __table_args__ = (
        CheckConstraint("banner_action::text = ANY (ARRAY['accepted_all'::character varying, 'rejected_all'::character varying, 'customised'::character varying]::text[])", name='cookie_preferences_banner_action_check'),
        ForeignKeyConstraint(['founder_id'], ['founders.founder_id'], ondelete='SET NULL', name='cookie_preferences_founder_id_fkey'),
        PrimaryKeyConstraint('preference_id', name='cookie_preferences_pkey'),
    )

    preference_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    necessary: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text('true'))
    analytics: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text('false'))
    marketing: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text('false'))
    functional: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text('false'))
    banner_shown: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text('false'))
    founder_id: Mapped[Optional[int]] = mapped_column(Integer)
    session_token: Mapped[Optional[str]] = mapped_column(String(200))
    banner_action: Mapped[Optional[str]] = mapped_column(String(20))
    created_at: Mapped[Optional[datetime.datetime]] = mapped_column(DateTime(True), server_default=text('now()'))
    updated_at: Mapped[Optional[datetime.datetime]] = mapped_column(DateTime(True), server_default=text('now()'))

    founder: Mapped[Optional['Founders']] = relationship('Founders', back_populates='cookie_preferences')


class DataDeletionRequests(Base):
    __tablename__ = 'data_deletion_requests'
    __table_args__ = (
        CheckConstraint("status::text = ANY (ARRAY['pending_otp'::character varying, 'grace_period'::character varying, 'processing'::character varying, 'completed'::character varying, 'cancelled'::character varying]::text[])", name='data_deletion_requests_status_check'),
        ForeignKeyConstraint(['founder_id'], ['founders.founder_id'], name='data_deletion_requests_founder_id_fkey'),
        PrimaryKeyConstraint('deletion_id', name='data_deletion_requests_pkey'),
        UniqueConstraint('founder_id', name='data_deletion_requests_founder_id_key'),
    )

    deletion_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    founder_id: Mapped[int] = mapped_column(Integer, nullable=False)
    requested_at: Mapped[datetime.datetime] = mapped_column(DateTime(True), nullable=False, server_default=text('now()'))
    otp_verified: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text('false'))
    status: Mapped[str] = mapped_column(String(20), nullable=False, server_default=text("'pending_otp'::character varying"))
    confirmation_email_sent: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text('false'))
    grace_period_ends_at: Mapped[Optional[datetime.datetime]] = mapped_column(DateTime(True))
    otp_verified_at: Mapped[Optional[datetime.datetime]] = mapped_column(DateTime(True))
    cancellation_requested_at: Mapped[Optional[datetime.datetime]] = mapped_column(DateTime(True))
    deletion_completed_at: Mapped[Optional[datetime.datetime]] = mapped_column(DateTime(True))
    data_types_deleted: Mapped[Optional[dict]] = mapped_column(JSONB, server_default=text("'{}'::jsonb"))
    created_at: Mapped[Optional[datetime.datetime]] = mapped_column(DateTime(True), server_default=text('now()'))

    founder: Mapped['Founders'] = relationship('Founders', back_populates='data_deletion_requests')


class DiscoveryCalls(Base):
    __tablename__ = 'discovery_calls'
    __table_args__ = (
        CheckConstraint("status::text = ANY (ARRAY['pending'::character varying, 'confirmed'::character varying, 'completed'::character varying, 'cancelled'::character varying, 'rescheduled'::character varying, 'no_show'::character varying]::text[])", name='discovery_calls_status_check'),
        ForeignKeyConstraint(['founder_id'], ['founders.founder_id'], name='discovery_calls_founder_id_fkey'),
        ForeignKeyConstraint(['rescheduled_from_call_id'], ['discovery_calls.call_id'], name='discovery_calls_rescheduled_from_call_id_fkey'),
        PrimaryKeyConstraint('call_id', name='discovery_calls_pkey'),
        Index('idx_discovery_calls_founder', 'founder_id'),
        Index('idx_discovery_calls_status', 'status'),
    )

    call_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    founder_id: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, server_default=text("'pending'::character varying"))
    scheduled_at: Mapped[datetime.datetime] = mapped_column(DateTime(True), nullable=False)
    duration_minutes: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text('45'))
    timezone: Mapped[str] = mapped_column(String(100), nullable=False, server_default=text("'Asia/Kolkata'::character varying"))
    reminder_sent_24h: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text('false'))
    reminder_sent_1h: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text('false'))
    meeting_link: Mapped[Optional[str]] = mapped_column(String(500))
    goxml_host: Mapped[Optional[str]] = mapped_column(String(100))
    booking_source: Mapped[Optional[str]] = mapped_column(String(50))
    report_id: Mapped[Optional[int]] = mapped_column(Integer)
    notes_pre_call: Mapped[Optional[str]] = mapped_column(Text)
    notes_post_call: Mapped[Optional[str]] = mapped_column(Text)
    cancelled_at: Mapped[Optional[datetime.datetime]] = mapped_column(DateTime(True))
    cancellation_reason: Mapped[Optional[str]] = mapped_column(Text)
    rescheduled_from_call_id: Mapped[Optional[int]] = mapped_column(Integer)
    completed_at: Mapped[Optional[datetime.datetime]] = mapped_column(DateTime(True))
    created_at: Mapped[Optional[datetime.datetime]] = mapped_column(DateTime(True), server_default=text('now()'))
    updated_at: Mapped[Optional[datetime.datetime]] = mapped_column(DateTime(True), server_default=text('now()'))

    founder: Mapped['Founders'] = relationship('Founders', back_populates='discovery_calls')
    rescheduled_from_call: Mapped[Optional['DiscoveryCalls']] = relationship('DiscoveryCalls', remote_side=[call_id], back_populates='rescheduled_from_call_reverse')
    rescheduled_from_call_reverse: Mapped[list['DiscoveryCalls']] = relationship('DiscoveryCalls', remote_side=[rescheduled_from_call_id], back_populates='rescheduled_from_call')
    admin_notes: Mapped[list['AdminNotes']] = relationship('AdminNotes', back_populates='linked_call')


class FounderContext(Base):
    __tablename__ = 'founder_context'
    __table_args__ = (
        CheckConstraint("economic_background::text = ANY (ARRAY['business_family'::character varying, 'salaried'::character varying, 'financial_stress'::character varying, 'stable'::character varying]::text[])", name='founder_context_economic_background_check'),
        CheckConstraint("education_level::text = ANY (ARRAY['no_degree'::character varying, 'technical'::character varying, 'business'::character varying, 'first_gen_graduate'::character varying]::text[])", name='founder_context_education_level_check'),
        CheckConstraint("geographic_type::text = ANY (ARRAY['metro'::character varying, 'tier2'::character varying, 'tier3'::character varying, 'rural'::character varying]::text[])", name='founder_context_geographic_type_check'),
        CheckConstraint("industry_exposure::text = ANY (ARRAY['none'::character varying, 'adjacent'::character varying, 'deep_domain'::character varying, 'first_gen_in_sector'::character varying]::text[])", name='founder_context_industry_exposure_check'),
        CheckConstraint("language_comfort::text = ANY (ARRAY['english_confident'::character varying, 'regional_primary'::character varying, 'bilingual'::character varying, 'technical_only'::character varying]::text[])", name='founder_context_language_comfort_check'),
        CheckConstraint("network_access::text = ANY (ARRAY['strong'::character varying, 'moderate'::character varying, 'limited'::character varying, 'none'::character varying]::text[])", name='founder_context_network_access_check'),
        ForeignKeyConstraint(['founder_id'], ['founders.founder_id'], ondelete='CASCADE', name='founder_context_founder_id_fkey'),
        PrimaryKeyConstraint('context_id', name='founder_context_pkey'),
        UniqueConstraint('founder_id', name='founder_context_founder_id_key'),
    )

    context_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    founder_id: Mapped[int] = mapped_column(Integer, nullable=False)
    geographic_type: Mapped[Optional[str]] = mapped_column(String(30))
    economic_background: Mapped[Optional[str]] = mapped_column(String(50))
    education_level: Mapped[Optional[str]] = mapped_column(String(50))
    industry_exposure: Mapped[Optional[str]] = mapped_column(String(50))
    language_comfort: Mapped[Optional[str]] = mapped_column(String(50))
    network_access: Mapped[Optional[str]] = mapped_column(String(20))
    context_notes: Mapped[Optional[str]] = mapped_column(Text)
    created_at: Mapped[Optional[datetime.datetime]] = mapped_column(DateTime(True), server_default=text('now()'))
    updated_at: Mapped[Optional[datetime.datetime]] = mapped_column(DateTime(True), server_default=text('now()'))

    founder: Mapped['Founders'] = relationship('Founders', back_populates='founder_context')


class FounderDimensionProfile(Base):
    __tablename__ = 'founder_dimension_profile'
    __table_args__ = (
        CheckConstraint("source::text = ANY (ARRAY['onboarding'::character varying, 'settings_update'::character varying, 'behavioral_tracking'::character varying, 'diagnosis_session'::character varying]::text[])", name='founder_dimension_profile_source_check'),
        ForeignKeyConstraint(['dimension_id'], ['founder_dimensions.dimension_id'], name='founder_dimension_profile_dimension_id_fkey'),
        ForeignKeyConstraint(['founder_id'], ['founders.founder_id'], ondelete='CASCADE', name='founder_dimension_profile_founder_id_fkey'),
        PrimaryKeyConstraint('profile_id', name='founder_dimension_profile_pkey'),
        Index('idx_fdp_current', 'founder_id', 'dimension_id', postgresql_where='(is_current = true)'),
        Index('idx_fdp_founder', 'founder_id'),
    )

    profile_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    founder_id: Mapped[int] = mapped_column(Integer, nullable=False)
    dimension_id: Mapped[int] = mapped_column(Integer, nullable=False)
    is_current: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text('true'))
    recorded_at: Mapped[datetime.datetime] = mapped_column(DateTime(True), nullable=False, server_default=text('now()'))
    created_at: Mapped[datetime.datetime] = mapped_column(DateTime(True), nullable=False, server_default=text('now()'))
    internal_score: Mapped[Optional[decimal.Decimal]] = mapped_column(Numeric(5, 2))
    display_value: Mapped[Optional[str]] = mapped_column(Text)
    confidence_score: Mapped[Optional[decimal.Decimal]] = mapped_column(Numeric(4, 3))
    source: Mapped[Optional[str]] = mapped_column(String(30))

    dimension: Mapped['FounderDimensions'] = relationship('FounderDimensions', back_populates='founder_dimension_profile')
    founder: Mapped['Founders'] = relationship('Founders', back_populates='founder_dimension_profile')


class FounderVisualChoices(Base):
    __tablename__ = 'founder_visual_choices'
    __table_args__ = (
        CheckConstraint("chosen_option = ANY (ARRAY['A'::bpchar, 'B'::bpchar])", name='founder_visual_choices_chosen_option_check'),
        ForeignKeyConstraint(['founder_id'], ['founders.founder_id'], ondelete='CASCADE', name='founder_visual_choices_founder_id_fkey'),
        ForeignKeyConstraint(['visual_question_id'], ['visual_question_bank.visual_question_id'], name='founder_visual_choices_visual_question_id_fkey'),
        PrimaryKeyConstraint('choice_id', name='founder_visual_choices_pkey'),
        Index('idx_fvc_founder', 'founder_id'),
    )

    choice_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    founder_id: Mapped[int] = mapped_column(Integer, nullable=False)
    visual_question_id: Mapped[int] = mapped_column(Integer, nullable=False)
    chosen_option: Mapped[str] = mapped_column(CHAR(1), nullable=False)
    answered_at: Mapped[datetime.datetime] = mapped_column(DateTime(True), nullable=False, server_default=text('now()'))
    created_at: Mapped[datetime.datetime] = mapped_column(DateTime(True), nullable=False, server_default=text('now()'))

    founder: Mapped['Founders'] = relationship('Founders', back_populates='founder_visual_choices')
    visual_question: Mapped['VisualQuestionBank'] = relationship('VisualQuestionBank', back_populates='founder_visual_choices')


class Interventions(Base):
    __tablename__ = 'interventions'
    __table_args__ = (
        ForeignKeyConstraint(['problem_id'], ['problems.problem_id'], name='interventions_problem_id_fkey'),
        PrimaryKeyConstraint('intervention_id', name='interventions_pkey'),
        UniqueConstraint('intervention_code', name='interventions_intervention_code_key'),
        Index('idx_interventions_problem', 'problem_id'),
    )

    intervention_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    intervention_code: Mapped[str] = mapped_column(String(20), nullable=False)
    problem_id: Mapped[int] = mapped_column(Integer, nullable=False)
    root_cause_ids: Mapped[dict] = mapped_column(JSONB, nullable=False, server_default=text("'[]'::jsonb"))
    capability_domain: Mapped[str] = mapped_column(String(100), nullable=False)
    section: Mapped[str] = mapped_column(String(100), nullable=False)
    recommended_frameworks: Mapped[dict] = mapped_column(JSONB, nullable=False, server_default=text("'[]'::jsonb"))
    immediate_next_steps: Mapped[dict] = mapped_column(JSONB, nullable=False, server_default=text("'[]'::jsonb"))
    framework_codes: Mapped[Optional[dict]] = mapped_column(JSONB, server_default=text("'[]'::jsonb"))
    stage_relevance: Mapped[Optional[dict]] = mapped_column(JSONB, server_default=text("'[]'::jsonb"))
    industry_relevance: Mapped[Optional[dict]] = mapped_column(JSONB, server_default=text("'[]'::jsonb"))
    design_principles: Mapped[Optional[dict]] = mapped_column(JSONB, server_default=text("'[]'::jsonb"))
    created_at: Mapped[Optional[datetime.datetime]] = mapped_column(DateTime(True), server_default=text('now()'))
    updated_at: Mapped[Optional[datetime.datetime]] = mapped_column(DateTime(True), server_default=text('now()'))

    problem: Mapped['Problems'] = relationship('Problems', back_populates='interventions')
    daily_actions: Mapped[list['DailyActions']] = relationship('DailyActions', back_populates='linked_intervention')
    founder_feedback: Mapped[list['FounderFeedback']] = relationship('FounderFeedback', back_populates='intervention')


class Notifications(Base):
    __tablename__ = 'notifications'
    __table_args__ = (
        CheckConstraint("channel::text = ANY (ARRAY['in_app'::character varying, 'email'::character varying]::text[])", name='notifications_channel_check'),
        CheckConstraint("type::text = ANY (ARRAY['report_ready'::character varying, 'diagnosis_reminder'::character varying, 'discovery_call_reminder'::character varying, 'follow_up'::character varying, 'product_update'::character varying, 'token_limit_reached'::character varying, 'subscription_expiring'::character varying, 'payment_failed'::character varying]::text[])", name='notifications_type_check'),
        ForeignKeyConstraint(['founder_id'], ['founders.founder_id'], ondelete='CASCADE', name='notifications_founder_id_fkey'),
        PrimaryKeyConstraint('notification_id', name='notifications_pkey'),
        Index('idx_notifications_founder', 'founder_id'),
        Index('idx_notifications_unread', 'founder_id', 'is_read', postgresql_where='(is_read = false)'),
    )

    notification_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    founder_id: Mapped[int] = mapped_column(Integer, nullable=False)
    type: Mapped[str] = mapped_column(String(50), nullable=False)
    channel: Mapped[str] = mapped_column(String(20), nullable=False)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    body: Mapped[str] = mapped_column(Text, nullable=False)
    is_read: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text('false'))
    action_url: Mapped[Optional[str]] = mapped_column(String(500))
    read_at: Mapped[Optional[datetime.datetime]] = mapped_column(DateTime(True))
    sent_at: Mapped[Optional[datetime.datetime]] = mapped_column(DateTime(True))
    metadata_: Mapped[Optional[dict]] = mapped_column('metadata', JSONB, server_default=text("'{}'::jsonb"))
    created_at: Mapped[Optional[datetime.datetime]] = mapped_column(DateTime(True), server_default=text('now()'))

    founder: Mapped['Founders'] = relationship('Founders', back_populates='notifications')


class PrivacyRequests(Base):
    __tablename__ = 'privacy_requests'
    __table_args__ = (
        CheckConstraint("request_type::text = ANY (ARRAY['view_data'::character varying, 'download_data'::character varying, 'correct_data'::character varying, 'withdraw_consent'::character varying, 'restrict_processing'::character varying, 'portability'::character varying]::text[])", name='privacy_requests_request_type_check'),
        CheckConstraint("status::text = ANY (ARRAY['pending'::character varying, 'in_progress'::character varying, 'completed'::character varying, 'rejected'::character varying]::text[])", name='privacy_requests_status_check'),
        ForeignKeyConstraint(['founder_id'], ['founders.founder_id'], name='privacy_requests_founder_id_fkey'),
        PrimaryKeyConstraint('request_id', name='privacy_requests_pkey'),
    )

    request_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    founder_id: Mapped[int] = mapped_column(Integer, nullable=False)
    request_type: Mapped[str] = mapped_column(String(30), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, server_default=text("'pending'::character varying"))
    requested_at: Mapped[datetime.datetime] = mapped_column(DateTime(True), nullable=False, server_default=text('now()'))
    request_details: Mapped[Optional[str]] = mapped_column(Text)
    processed_by: Mapped[Optional[str]] = mapped_column(String(100))
    processing_notes: Mapped[Optional[str]] = mapped_column(Text)
    rejection_reason: Mapped[Optional[str]] = mapped_column(Text)
    due_by: Mapped[Optional[datetime.datetime]] = mapped_column(DateTime(True))
    completed_at: Mapped[Optional[datetime.datetime]] = mapped_column(DateTime(True))
    created_at: Mapped[Optional[datetime.datetime]] = mapped_column(DateTime(True), server_default=text('now()'))

    founder: Mapped['Founders'] = relationship('Founders', back_populates='privacy_requests')


class ProblemStageMapping(Base):
    __tablename__ = 'problem_stage_mapping'
    __table_args__ = (
        CheckConstraint('prevalence_score >= 1 AND prevalence_score <= 10', name='problem_stage_mapping_prevalence_score_check'),
        ForeignKeyConstraint(['problem_id'], ['problems.problem_id'], name='problem_stage_mapping_problem_id_fkey'),
        ForeignKeyConstraint(['stage_id'], ['founder_stages.stage_id'], name='problem_stage_mapping_stage_id_fkey'),
        PrimaryKeyConstraint('mapping_id', name='problem_stage_mapping_pkey'),
        UniqueConstraint('problem_id', 'stage_id', name='problem_stage_mapping_problem_id_stage_id_key'),
        Index('idx_psm_problem', 'problem_id'),
        Index('idx_psm_stage', 'stage_id'),
    )

    mapping_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    problem_id: Mapped[int] = mapped_column(Integer, nullable=False)
    stage_id: Mapped[int] = mapped_column(Integer, nullable=False)
    prevalence_score: Mapped[int] = mapped_column(Integer, nullable=False)
    notes: Mapped[Optional[str]] = mapped_column(Text)

    problem: Mapped['Problems'] = relationship('Problems', back_populates='problem_stage_mapping')
    stage: Mapped['FounderStages'] = relationship('FounderStages', back_populates='problem_stage_mapping')


class ReportShares(Base):
    __tablename__ = 'report_shares'
    __table_args__ = (
        ForeignKeyConstraint(['founder_id'], ['founders.founder_id'], name='report_shares_founder_id_fkey'),
        PrimaryKeyConstraint('share_id', name='report_shares_pkey'),
        UniqueConstraint('share_token', name='report_shares_share_token_key'),
    )

    share_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    founder_id: Mapped[int] = mapped_column(Integer, nullable=False)
    report_id: Mapped[int] = mapped_column(Integer, nullable=False)
    share_token: Mapped[str] = mapped_column(String(200), nullable=False)
    share_url: Mapped[str] = mapped_column(Text, nullable=False)
    expires_at: Mapped[datetime.datetime] = mapped_column(DateTime(True), nullable=False, server_default=text("(now() + '30 days'::interval)"))
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text('true'))
    access_count: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text('0'))
    last_accessed_at: Mapped[Optional[datetime.datetime]] = mapped_column(DateTime(True))
    created_at: Mapped[Optional[datetime.datetime]] = mapped_column(DateTime(True), server_default=text('now()'))

    founder: Mapped['Founders'] = relationship('Founders', back_populates='report_shares')


class RootCauses(Base):
    __tablename__ = 'root_causes'
    __table_args__ = (
        CheckConstraint('confidence_weight >= 0.0 AND confidence_weight <= 1.0', name='root_causes_confidence_weight_check'),
        CheckConstraint("layer::text = ANY (ARRAY['internal'::character varying, 'external'::character varying]::text[])", name='root_causes_layer_check'),
        CheckConstraint("primary_stage_group::text = ANY (ARRAY['Stage 0'::character varying, 'Stage 0→1'::character varying, 'Stage 1→10+'::character varying]::text[])", name='root_causes_primary_stage_group_check'),
        CheckConstraint("root_cause_category::text = ANY (ARRAY['Psychological'::character varying, 'Knowledge'::character varying, 'Behavioural'::character varying, 'Strategic'::character varying, 'Operational'::character varying]::text[])", name='root_causes_root_cause_category_check'),
        ForeignKeyConstraint(['problem_id'], ['problems.problem_id'], name='root_causes_problem_id_fkey'),
        PrimaryKeyConstraint('root_cause_id', name='root_causes_pkey'),
        UniqueConstraint('root_cause_code', name='root_causes_root_cause_code_key'),
        Index('idx_root_causes_code', 'root_cause_code'),
        Index('idx_root_causes_embedding', 'embedding', postgresql_ops={'embedding': 'vector_cosine_ops'}, postgresql_using='hnsw', postgresql_where='(embedding IS NOT NULL)'),
        Index('idx_root_causes_problem', 'problem_id'),
        Index('idx_root_causes_stage_group', 'primary_stage_group'),
    )

    root_cause_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    root_cause_code: Mapped[str] = mapped_column(String(20), nullable=False)
    problem_id: Mapped[int] = mapped_column(Integer, nullable=False)
    root_cause_name: Mapped[str] = mapped_column(String(200), nullable=False)
    root_cause_category: Mapped[str] = mapped_column(String(50), nullable=False)
    explanation: Mapped[str] = mapped_column(Text, nullable=False)
    confidence_weight: Mapped[decimal.Decimal] = mapped_column(Numeric(5, 2), nullable=False)
    layer: Mapped[str] = mapped_column(String(20), nullable=False)
    embedding: Mapped[Optional[Any]] = mapped_column(Vector(384))
    created_at: Mapped[Optional[datetime.datetime]] = mapped_column(DateTime(True), server_default=text('now()'))
    updated_at: Mapped[Optional[datetime.datetime]] = mapped_column(DateTime(True), server_default=text('now()'))
    primary_stage_group: Mapped[Optional[str]] = mapped_column(String(20))

    problem: Mapped['Problems'] = relationship('Problems', back_populates='root_causes')
    questions: Mapped[list['Questions']] = relationship('Questions', back_populates='root_cause')
    root_cause_weights: Mapped[list['RootCauseWeights']] = relationship('RootCauseWeights', back_populates='root_cause')
    answers: Mapped[list['Answers']] = relationship('Answers', back_populates='root_cause_hypothesis')
    detected_root_causes: Mapped[list['DetectedRootCauses']] = relationship('DetectedRootCauses', back_populates='root_cause')


class Subscriptions(Base):
    __tablename__ = 'subscriptions'
    __table_args__ = (
        CheckConstraint("billing_cycle::text = ANY (ARRAY['monthly'::character varying, 'annual'::character varying]::text[])", name='subscriptions_billing_cycle_check'),
        CheckConstraint("plan_type::text = ANY (ARRAY['free'::character varying, 'starter'::character varying, 'pro'::character varying, 'enterprise'::character varying]::text[])", name='subscriptions_plan_type_check'),
        CheckConstraint("status::text = ANY (ARRAY['active'::character varying, 'cancelled'::character varying, 'expired'::character varying, 'paused'::character varying, 'trial'::character varying]::text[])", name='subscriptions_status_check'),
        ForeignKeyConstraint(['founder_id'], ['founders.founder_id'], name='subscriptions_founder_id_fkey'),
        PrimaryKeyConstraint('subscription_id', name='subscriptions_pkey'),
        Index('idx_subscriptions_founder', 'founder_id'),
    )

    subscription_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    founder_id: Mapped[int] = mapped_column(Integer, nullable=False)
    plan_type: Mapped[str] = mapped_column(String(20), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False)
    started_at: Mapped[datetime.datetime] = mapped_column(DateTime(True), nullable=False, server_default=text('now()'))
    billing_cycle: Mapped[Optional[str]] = mapped_column(String(20))
    amount_inr: Mapped[Optional[decimal.Decimal]] = mapped_column(Numeric(10, 2))
    expires_at: Mapped[Optional[datetime.datetime]] = mapped_column(DateTime(True))
    cancelled_at: Mapped[Optional[datetime.datetime]] = mapped_column(DateTime(True))
    cancellation_reason: Mapped[Optional[str]] = mapped_column(Text)
    trial_ends_at: Mapped[Optional[datetime.datetime]] = mapped_column(DateTime(True))
    payment_gateway: Mapped[Optional[str]] = mapped_column(String(50))
    gateway_subscription_id: Mapped[Optional[str]] = mapped_column(String(200))
    created_at: Mapped[Optional[datetime.datetime]] = mapped_column(DateTime(True), server_default=text('now()'))
    updated_at: Mapped[Optional[datetime.datetime]] = mapped_column(DateTime(True), server_default=text('now()'))

    founder: Mapped['Founders'] = relationship('Founders', back_populates='subscriptions')
    payments: Mapped[list['Payments']] = relationship('Payments', back_populates='subscription')


class UserTokenUsage(Base):
    __tablename__ = 'user_token_usage'
    __table_args__ = (
        ForeignKeyConstraint(['founder_id'], ['founders.founder_id'], ondelete='CASCADE', name='user_token_usage_founder_id_fkey'),
        PrimaryKeyConstraint('usage_id', name='user_token_usage_pkey'),
        UniqueConstraint('founder_id', 'usage_date', name='user_token_usage_founder_id_usage_date_key'),
    )

    usage_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    founder_id: Mapped[int] = mapped_column(Integer, nullable=False)
    usage_date: Mapped[datetime.date] = mapped_column(Date, nullable=False)
    tokens_used: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text('0'))
    tokens_limit: Mapped[int] = mapped_column(Integer, nullable=False)
    plan_type: Mapped[str] = mapped_column(String(20), nullable=False)
    limit_reached: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text('false'))
    reset_at: Mapped[datetime.datetime] = mapped_column(DateTime(True), nullable=False)
    limit_reached_at: Mapped[Optional[datetime.datetime]] = mapped_column(DateTime(True))
    created_at: Mapped[Optional[datetime.datetime]] = mapped_column(DateTime(True), server_default=text('now()'))

    founder: Mapped['Founders'] = relationship('Founders', back_populates='user_token_usage')


class WebhookLogs(Base):
    __tablename__ = 'webhook_logs'
    __table_args__ = (
        CheckConstraint("source::text = ANY (ARRAY['razorpay'::character varying, 'calendly'::character varying, 'stripe'::character varying, 'other'::character varying]::text[])", name='webhook_logs_source_check'),
        CheckConstraint("status::text = ANY (ARRAY['received'::character varying, 'processing'::character varying, 'processed'::character varying, 'failed'::character varying]::text[])", name='webhook_logs_status_check'),
        ForeignKeyConstraint(['founder_id'], ['founders.founder_id'], ondelete='SET NULL', name='webhook_logs_founder_id_fkey'),
        PrimaryKeyConstraint('log_id', name='webhook_logs_pkey'),
        UniqueConstraint('gateway_event_id', name='webhook_logs_gateway_event_id_key'),
        Index('idx_webhook_gateway_event', 'gateway_event_id'),
        Index('idx_webhook_status', 'status'),
    )

    log_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    source: Mapped[str] = mapped_column(String(50), nullable=False)
    event_type: Mapped[str] = mapped_column(String(100), nullable=False)
    gateway_event_id: Mapped[str] = mapped_column(String(200), nullable=False)
    payload: Mapped[dict] = mapped_column(JSONB, nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, server_default=text("'received'::character varying"))
    retry_count: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text('0'))
    founder_id: Mapped[Optional[int]] = mapped_column(Integer)
    related_entity: Mapped[Optional[str]] = mapped_column(String(50))
    related_entity_id: Mapped[Optional[int]] = mapped_column(Integer)
    error_message: Mapped[Optional[str]] = mapped_column(Text)
    processed_at: Mapped[Optional[datetime.datetime]] = mapped_column(DateTime(True))
    created_at: Mapped[Optional[datetime.datetime]] = mapped_column(DateTime(True), server_default=text('now()'))

    founder: Mapped[Optional['Founders']] = relationship('Founders', back_populates='webhook_logs')


class AdminNotes(Base):
    __tablename__ = 'admin_notes'
    __table_args__ = (
        CheckConstraint("note_type::text = ANY (ARRAY['general'::character varying, 'pre_call'::character varying, 'post_call'::character varying, 'risk_flag'::character varying, 'opportunity'::character varying, 'follow_up'::character varying]::text[])", name='admin_notes_note_type_check'),
        ForeignKeyConstraint(['founder_id'], ['founders.founder_id'], name='admin_notes_founder_id_fkey'),
        ForeignKeyConstraint(['linked_call_id'], ['discovery_calls.call_id'], name='admin_notes_linked_call_id_fkey'),
        PrimaryKeyConstraint('note_id', name='admin_notes_pkey'),
    )

    note_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    founder_id: Mapped[int] = mapped_column(Integer, nullable=False)
    created_by: Mapped[str] = mapped_column(String(100), nullable=False)
    note_type: Mapped[str] = mapped_column(String(30), nullable=False)
    note_content: Mapped[str] = mapped_column(Text, nullable=False)
    is_pinned: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text('false'))
    linked_call_id: Mapped[Optional[int]] = mapped_column(Integer)
    created_at: Mapped[Optional[datetime.datetime]] = mapped_column(DateTime(True), server_default=text('now()'))
    updated_at: Mapped[Optional[datetime.datetime]] = mapped_column(DateTime(True), server_default=text('now()'))

    founder: Mapped['Founders'] = relationship('Founders', back_populates='admin_notes')
    linked_call: Mapped[Optional['DiscoveryCalls']] = relationship('DiscoveryCalls', back_populates='admin_notes')


class DailyActions(Base):
    __tablename__ = 'daily_actions'
    __table_args__ = (
        CheckConstraint("priority::text = ANY (ARRAY['high'::character varying, 'medium'::character varying, 'low'::character varying]::text[])", name='daily_actions_priority_check'),
        CheckConstraint("source::text = ANY (ARRAY['manual'::character varying, 'ai_generated'::character varying, 'report_recommendation'::character varying]::text[])", name='daily_actions_source_check'),
        ForeignKeyConstraint(['founder_id'], ['founders.founder_id'], ondelete='CASCADE', name='daily_actions_founder_id_fkey'),
        ForeignKeyConstraint(['linked_intervention_id'], ['interventions.intervention_id'], name='daily_actions_linked_intervention_id_fkey'),
        PrimaryKeyConstraint('action_id', name='daily_actions_pkey'),
        Index('idx_daily_actions_founder_date', 'founder_id', 'action_date'),
        Index('idx_daily_actions_founder_incomplete', 'founder_id', postgresql_where='(is_completed = false)'),
    )

    action_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    founder_id: Mapped[int] = mapped_column(Integer, nullable=False)
    action_date: Mapped[datetime.date] = mapped_column(Date, nullable=False, server_default=text('CURRENT_DATE'))
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    priority: Mapped[str] = mapped_column(String(20), nullable=False, server_default=text("'medium'::character varying"))
    is_completed: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text('false'))
    source: Mapped[str] = mapped_column(String(30), nullable=False, server_default=text("'manual'::character varying"))
    display_order: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text('0'))
    created_at: Mapped[datetime.datetime] = mapped_column(DateTime(True), nullable=False, server_default=text('now()'))
    updated_at: Mapped[datetime.datetime] = mapped_column(DateTime(True), nullable=False, server_default=text('now()'))
    description: Mapped[Optional[str]] = mapped_column(Text)
    due_date: Mapped[Optional[datetime.date]] = mapped_column(Date)
    completed_at: Mapped[Optional[datetime.datetime]] = mapped_column(DateTime(True))
    linked_intervention_id: Mapped[Optional[int]] = mapped_column(Integer)

    founder: Mapped['Founders'] = relationship('Founders', back_populates='daily_actions')
    linked_intervention: Mapped[Optional['Interventions']] = relationship('Interventions', back_populates='daily_actions')


class FileUploads(Base):
    __tablename__ = 'file_uploads'
    __table_args__ = (
        CheckConstraint("upload_category::text = ANY (ARRAY['file'::character varying, 'image'::character varying]::text[])", name='file_uploads_upload_category_check'),
        ForeignKeyConstraint(['conversation_id'], ['conversations.conversation_id'], name='file_uploads_conversation_id_fkey'),
        ForeignKeyConstraint(['founder_id'], ['founders.founder_id'], name='file_uploads_founder_id_fkey'),
        PrimaryKeyConstraint('upload_id', name='file_uploads_pkey'),
    )

    upload_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    founder_id: Mapped[int] = mapped_column(Integer, nullable=False)
    conversation_id: Mapped[int] = mapped_column(Integer, nullable=False)
    file_name: Mapped[str] = mapped_column(String(300), nullable=False)
    file_type: Mapped[str] = mapped_column(String(50), nullable=False)
    file_size_bytes: Mapped[int] = mapped_column(Integer, nullable=False)
    storage_path: Mapped[str] = mapped_column(String(500), nullable=False)
    upload_category: Mapped[str] = mapped_column(String(20), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text('true'))
    message_id: Mapped[Optional[int]] = mapped_column(Integer)
    storage_url: Mapped[Optional[str]] = mapped_column(Text)
    created_at: Mapped[Optional[datetime.datetime]] = mapped_column(DateTime(True), server_default=text('now()'))

    conversation: Mapped['Conversations'] = relationship('Conversations', back_populates='file_uploads')
    founder: Mapped['Founders'] = relationship('Founders', back_populates='file_uploads')


class Payments(Base):
    __tablename__ = 'payments'
    __table_args__ = (
        CheckConstraint("status::text = ANY (ARRAY['pending'::character varying, 'success'::character varying, 'failed'::character varying, 'refunded'::character varying]::text[])", name='payments_status_check'),
        ForeignKeyConstraint(['founder_id'], ['founders.founder_id'], name='payments_founder_id_fkey'),
        ForeignKeyConstraint(['subscription_id'], ['subscriptions.subscription_id'], name='payments_subscription_id_fkey'),
        PrimaryKeyConstraint('payment_id', name='payments_pkey'),
        Index('idx_payments_founder', 'founder_id'),
    )

    payment_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    founder_id: Mapped[int] = mapped_column(Integer, nullable=False)
    amount_inr: Mapped[decimal.Decimal] = mapped_column(Numeric(10, 2), nullable=False)
    currency: Mapped[str] = mapped_column(String(5), nullable=False, server_default=text("'INR'::character varying"))
    status: Mapped[str] = mapped_column(String(20), nullable=False)
    payment_gateway: Mapped[str] = mapped_column(String(50), nullable=False)
    subscription_id: Mapped[Optional[int]] = mapped_column(Integer)
    gateway_payment_id: Mapped[Optional[str]] = mapped_column(String(200))
    gateway_order_id: Mapped[Optional[str]] = mapped_column(String(200))
    invoice_url: Mapped[Optional[str]] = mapped_column(Text)
    invoice_number: Mapped[Optional[str]] = mapped_column(String(50))
    failure_reason: Mapped[Optional[str]] = mapped_column(Text)
    paid_at: Mapped[Optional[datetime.datetime]] = mapped_column(DateTime(True))
    refunded_at: Mapped[Optional[datetime.datetime]] = mapped_column(DateTime(True))
    created_at: Mapped[Optional[datetime.datetime]] = mapped_column(DateTime(True), server_default=text('now()'))

    founder: Mapped['Founders'] = relationship('Founders', back_populates='payments')
    subscription: Mapped[Optional['Subscriptions']] = relationship('Subscriptions', back_populates='payments')


class Questions(Base):
    __tablename__ = 'questions'
    __table_args__ = (
        CheckConstraint('difficulty_level >= 1 AND difficulty_level <= 5', name='questions_difficulty_level_check'),
        CheckConstraint("primary_stage_group::text = ANY (ARRAY['Stage 0'::character varying, 'Stage 0→1'::character varying, 'Stage 1→10+'::character varying]::text[])", name='questions_primary_stage_group_check'),
        CheckConstraint("priority::text = ANY (ARRAY['CORE'::character varying, 'SUPPLEMENTARY'::character varying]::text[])", name='questions_priority_check'),
        CheckConstraint("question_type::text = ANY (ARRAY['open_text'::character varying, 'rating_scale'::character varying, 'yes_no'::character varying, 'multiple_choice'::character varying]::text[])", name='questions_question_type_check'),
        ForeignKeyConstraint(['follow_up_question_id'], ['questions.question_id'], name='questions_follow_up_question_id_fkey'),
        ForeignKeyConstraint(['problem_id'], ['problems.problem_id'], name='questions_problem_id_fkey'),
        ForeignKeyConstraint(['root_cause_id'], ['root_causes.root_cause_id'], name='questions_root_cause_id_fkey'),
        PrimaryKeyConstraint('question_id', name='questions_pkey'),
        UniqueConstraint('question_code', name='questions_question_code_key'),
        Index('idx_questions_category', 'category'),
        Index('idx_questions_code', 'question_code'),
        Index('idx_questions_distress', 'is_distress_tagged'),
        Index('idx_questions_embedding', 'embedding', postgresql_ops={'embedding': 'vector_cosine_ops'}, postgresql_using='hnsw', postgresql_where='(embedding IS NOT NULL)'),
        Index('idx_questions_priority', 'priority'),
        Index('idx_questions_stage_group', 'primary_stage_group'),
    )

    question_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    question_code: Mapped[str] = mapped_column(String(100), nullable=False)
    category: Mapped[str] = mapped_column(String(100), nullable=False)
    question_text: Mapped[str] = mapped_column(Text, nullable=False)
    problem_id: Mapped[int] = mapped_column(Integer, nullable=False)
    root_cause_id: Mapped[int] = mapped_column(Integer, nullable=False)
    question_type: Mapped[str] = mapped_column(String(30), nullable=False)
    difficulty_level: Mapped[int] = mapped_column(Integer, nullable=False)
    priority: Mapped[str] = mapped_column(String(20), nullable=False)
    is_distress_tagged: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text('false'))
    red_flag_pattern: Mapped[Optional[str]] = mapped_column(Text)
    green_flag_pattern: Mapped[Optional[str]] = mapped_column(Text)
    follow_up_question_id: Mapped[Optional[int]] = mapped_column(Integer)
    embedding: Mapped[Optional[Any]] = mapped_column(Vector(384))
    created_at: Mapped[Optional[datetime.datetime]] = mapped_column(DateTime(True), server_default=text('now()'))
    updated_at: Mapped[Optional[datetime.datetime]] = mapped_column(DateTime(True), server_default=text('now()'))
    primary_stage_group: Mapped[Optional[str]] = mapped_column(String(20))

    follow_up_question: Mapped[Optional['Questions']] = relationship('Questions', remote_side=[question_id], back_populates='follow_up_question_reverse')
    follow_up_question_reverse: Mapped[list['Questions']] = relationship('Questions', remote_side=[follow_up_question_id], back_populates='follow_up_question')
    problem: Mapped['Problems'] = relationship('Problems', back_populates='questions')
    root_cause: Mapped['RootCauses'] = relationship('RootCauses', back_populates='questions')
    question_tag_mapping: Mapped[list['QuestionTagMapping']] = relationship('QuestionTagMapping', back_populates='question')
    sessions: Mapped[list['Sessions']] = relationship('Sessions', back_populates='current_question')
    answers_question: Mapped[list['Answers']] = relationship('Answers', foreign_keys='[Answers.question_id]', back_populates='question')
    answers_triggered_follow_up: Mapped[list['Answers']] = relationship('Answers', foreign_keys='[Answers.triggered_follow_up_id]', back_populates='triggered_follow_up')


class RootCauseWeights(Base):
    __tablename__ = 'root_cause_weights'
    __table_args__ = (
        CheckConstraint('stage_weight = ANY (ARRAY[0.5, 1.0, 1.5, 2.0])', name='root_cause_weights_stage_weight_check'),
        ForeignKeyConstraint(['root_cause_id'], ['root_causes.root_cause_id'], name='root_cause_weights_root_cause_id_fkey'),
        ForeignKeyConstraint(['stage_id'], ['founder_stages.stage_id'], name='root_cause_weights_stage_id_fkey'),
        PrimaryKeyConstraint('weight_id', name='root_cause_weights_pkey'),
        UniqueConstraint('root_cause_id', 'stage_id', name='root_cause_weights_root_cause_id_stage_id_key'),
        Index('idx_rcw_root_cause', 'root_cause_id'),
        Index('idx_rcw_stage', 'stage_id'),
    )

    weight_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    root_cause_id: Mapped[int] = mapped_column(Integer, nullable=False)
    stage_id: Mapped[int] = mapped_column(Integer, nullable=False)
    stage_weight: Mapped[decimal.Decimal] = mapped_column(Numeric(5, 2), nullable=False)
    notes: Mapped[Optional[str]] = mapped_column(Text)

    root_cause: Mapped['RootCauses'] = relationship('RootCauses', back_populates='root_cause_weights')
    stage: Mapped['FounderStages'] = relationship('FounderStages', back_populates='root_cause_weights')


class QuestionTagMapping(Base):
    __tablename__ = 'question_tag_mapping'
    __table_args__ = (
        ForeignKeyConstraint(['question_id'], ['questions.question_id'], name='question_tag_mapping_question_id_fkey'),
        ForeignKeyConstraint(['tag_id'], ['question_tags.tag_id'], name='question_tag_mapping_tag_id_fkey'),
        PrimaryKeyConstraint('mapping_id', name='question_tag_mapping_pkey'),
        UniqueConstraint('question_id', 'tag_id', name='question_tag_mapping_question_id_tag_id_key'),
        Index('idx_qtm_question', 'question_id'),
        Index('idx_qtm_tag', 'tag_id'),
    )

    mapping_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    question_id: Mapped[int] = mapped_column(Integer, nullable=False)
    tag_id: Mapped[int] = mapped_column(Integer, nullable=False)

    question: Mapped['Questions'] = relationship('Questions', back_populates='question_tag_mapping')
    tag: Mapped['QuestionTags'] = relationship('QuestionTags', back_populates='question_tag_mapping')


class Sessions(Base):
    __tablename__ = 'sessions'
    __table_args__ = (
        CheckConstraint("data_quality_status::text = ANY (ARRAY['unreviewed'::character varying, 'approved'::character varying, 'rejected'::character varying]::text[])", name='sessions_data_quality_status_check'),
        CheckConstraint('overall_confidence_score >= 0::numeric AND overall_confidence_score <= 100::numeric', name='sessions_overall_confidence_score_check'),
        CheckConstraint("routing_state::text = ANY (ARRAY['continue'::character varying, 'validate'::character varying, 'generate_report'::character varying]::text[])", name='sessions_routing_state_check'),
        CheckConstraint("session_state::text = ANY (ARRAY['stable'::character varying, 'significantly_guarded'::character varying, 'high_distress'::character varying]::text[])", name='sessions_session_state_check'),
        CheckConstraint("status::text = ANY (ARRAY['in_progress'::character varying, 'completed'::character varying, 'abandoned'::character varying]::text[])", name='sessions_status_check'),
        ForeignKeyConstraint(['current_question_id'], ['questions.question_id'], name='sessions_current_question_id_fkey'),
        ForeignKeyConstraint(['founder_id'], ['founders.founder_id'], ondelete='CASCADE', name='sessions_founder_id_fkey'),
        ForeignKeyConstraint(['founder_industry_id'], ['industries.industry_id'], name='sessions_founder_industry_id_fkey'),
        ForeignKeyConstraint(['founder_stage_id'], ['founder_stages.stage_id'], name='sessions_founder_stage_id_fkey'),
        PrimaryKeyConstraint('session_id', name='sessions_pkey'),
        Index('idx_sessions_founder', 'founder_id'),
        Index('idx_sessions_quality_status', 'data_quality_status', postgresql_where="((data_quality_status)::text = 'approved'::text)"),
        Index('idx_sessions_status', 'status'),
    )

    session_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    founder_id: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, server_default=text("'in_progress'::character varying"))
    questions_answered_count: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text('0'))
    category_risk_scores: Mapped[dict] = mapped_column(JSONB, nullable=False, server_default=text("'{}'::jsonb"))
    session_distress_score: Mapped[decimal.Decimal] = mapped_column(Numeric(6, 2), nullable=False, server_default=text('0'))
    distress_mode_triggered: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text('false'))
    started_at: Mapped[datetime.datetime] = mapped_column(DateTime(True), nullable=False, server_default=text('now()'))
    last_activity_at: Mapped[datetime.datetime] = mapped_column(DateTime(True), nullable=False, server_default=text('now()'))
    created_at: Mapped[datetime.datetime] = mapped_column(DateTime(True), nullable=False, server_default=text('now()'))
    updated_at: Mapped[datetime.datetime] = mapped_column(DateTime(True), nullable=False, server_default=text('now()'))
    data_quality_status: Mapped[str] = mapped_column(String(15), nullable=False, server_default=text("'unreviewed'::character varying"))
    current_category: Mapped[Optional[str]] = mapped_column(String(50))
    current_question_id: Mapped[Optional[int]] = mapped_column(Integer)
    session_state: Mapped[Optional[str]] = mapped_column(String(30), server_default=text("'stable'::character varying"))
    founder_stage_id: Mapped[Optional[int]] = mapped_column(Integer)
    founder_industry_id: Mapped[Optional[int]] = mapped_column(Integer)
    completed_at: Mapped[Optional[datetime.datetime]] = mapped_column(DateTime(True))
    overall_confidence_score: Mapped[Optional[decimal.Decimal]] = mapped_column(Numeric(5, 2), server_default=text('0'), comment='Outer-layer rolled-up confidence (0-100), derived from inner-layer per-question scoring (answers.score) and the 4-factor weighted root cause ranking. Drives routing_state.')
    routing_state: Mapped[Optional[str]] = mapped_column(String(20), server_default=text("'continue'::character varying"), comment='continue (<60%) = keep asking questions. validate (60-80%) = present hypothesis to founder for confirmation. generate_report (>80%) = sufficient confidence to produce the Founder Clarity Report.')
    reviewed_by: Mapped[Optional[str]] = mapped_column(String(100))
    reviewed_at: Mapped[Optional[datetime.datetime]] = mapped_column(DateTime(True))
    training_notes: Mapped[Optional[str]] = mapped_column(Text)

    current_question: Mapped[Optional['Questions']] = relationship('Questions', back_populates='sessions')
    founder: Mapped['Founders'] = relationship('Founders', back_populates='sessions')
    founder_industry: Mapped[Optional['Industries']] = relationship('Industries', back_populates='sessions')
    founder_stage: Mapped[Optional['FounderStages']] = relationship('FounderStages', back_populates='sessions')
    answers: Mapped[list['Answers']] = relationship('Answers', back_populates='session')
    detected_root_causes: Mapped[list['DetectedRootCauses']] = relationship('DetectedRootCauses', back_populates='session')
    founder_reports: Mapped[list['FounderReports']] = relationship('FounderReports', back_populates='session')
    rag_retrieval_log: Mapped[list['RagRetrievalLog']] = relationship('RagRetrievalLog', back_populates='session')
    stage_assessments: Mapped[list['StageAssessments']] = relationship('StageAssessments', back_populates='session')
    founder_feedback: Mapped[list['FounderFeedback']] = relationship('FounderFeedback', back_populates='session')
    internal_intelligence_reports: Mapped[list['InternalIntelligenceReports']] = relationship('InternalIntelligenceReports', back_populates='session')


class Answers(Base):
    __tablename__ = 'answers'
    __table_args__ = (
        CheckConstraint("confirmation_status::text = ANY (ARRAY['confirmed'::character varying, 'unconfirmed'::character varying, 'not_tested'::character varying]::text[])", name='answers_confirmation_status_check'),
        CheckConstraint('score = ANY (ARRAY[0::numeric, 1::numeric, 2::numeric])', name='answers_score_check'),
        CheckConstraint("score_label::text = ANY (ARRAY['green'::character varying, 'amber'::character varying, 'red'::character varying]::text[])", name='answers_score_label_check'),
        ForeignKeyConstraint(['founder_id'], ['founders.founder_id'], ondelete='CASCADE', name='answers_founder_id_fkey'),
        ForeignKeyConstraint(['question_id'], ['questions.question_id'], name='answers_question_id_fkey'),
        ForeignKeyConstraint(['root_cause_hypothesis_id'], ['root_causes.root_cause_id'], name='answers_root_cause_hypothesis_id_fkey'),
        ForeignKeyConstraint(['session_id'], ['sessions.session_id'], ondelete='CASCADE', name='answers_session_id_fkey'),
        ForeignKeyConstraint(['triggered_follow_up_id'], ['questions.question_id'], name='answers_triggered_follow_up_id_fkey'),
        PrimaryKeyConstraint('answer_id', name='answers_pkey'),
        Index('idx_answers_founder', 'founder_id'),
        Index('idx_answers_question', 'question_id'),
        Index('idx_answers_root_cause', 'root_cause_hypothesis_id'),
        Index('idx_answers_session', 'session_id'),
    )

    answer_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    session_id: Mapped[int] = mapped_column(Integer, nullable=False)
    founder_id: Mapped[int] = mapped_column(Integer, nullable=False)
    question_id: Mapped[int] = mapped_column(Integer, nullable=False)
    answer_text: Mapped[str] = mapped_column(Text, nullable=False)
    is_follow_up: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text('false'))
    is_distress_flagged: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text('false'))
    answered_at: Mapped[datetime.datetime] = mapped_column(DateTime(True), nullable=False, server_default=text('now()'))
    created_at: Mapped[datetime.datetime] = mapped_column(DateTime(True), nullable=False, server_default=text('now()'))
    score: Mapped[Optional[decimal.Decimal]] = mapped_column(Numeric(3, 1))
    score_label: Mapped[Optional[str]] = mapped_column(String(10))
    triggered_follow_up_id: Mapped[Optional[int]] = mapped_column(Integer)
    root_cause_hypothesis_id: Mapped[Optional[int]] = mapped_column(Integer)
    confirmation_status: Mapped[Optional[str]] = mapped_column(String(15), server_default=text("'not_tested'::character varying"))

    founder: Mapped['Founders'] = relationship('Founders', back_populates='answers')
    question: Mapped['Questions'] = relationship('Questions', foreign_keys=[question_id], back_populates='answers_question')
    root_cause_hypothesis: Mapped[Optional['RootCauses']] = relationship('RootCauses', back_populates='answers')
    session: Mapped['Sessions'] = relationship('Sessions', back_populates='answers')
    triggered_follow_up: Mapped[Optional['Questions']] = relationship('Questions', foreign_keys=[triggered_follow_up_id], back_populates='answers_triggered_follow_up')


class DetectedRootCauses(Base):
    __tablename__ = 'detected_root_causes'
    __table_args__ = (
        CheckConstraint("confirmation_status::text = ANY (ARRAY['confirmed'::character varying, 'unconfirmed'::character varying, 'not_tested'::character varying]::text[])", name='detected_root_causes_confirmation_status_check'),
        ForeignKeyConstraint(['founder_id'], ['founders.founder_id'], ondelete='CASCADE', name='detected_root_causes_founder_id_fkey'),
        ForeignKeyConstraint(['root_cause_id'], ['root_causes.root_cause_id'], name='detected_root_causes_root_cause_id_fkey'),
        ForeignKeyConstraint(['session_id'], ['sessions.session_id'], ondelete='CASCADE', name='detected_root_causes_session_id_fkey'),
        PrimaryKeyConstraint('detection_id', name='detected_root_causes_pkey'),
        Index('idx_detected_rc_founder', 'founder_id'),
        Index('idx_detected_rc_session', 'session_id'),
        Index('idx_detected_rc_top', 'session_id', postgresql_where='(is_top_finding = true)'),
        Index('uq_detected_rc_session_rootcause', 'session_id', 'root_cause_id', unique=True),
    )

    detection_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    session_id: Mapped[int] = mapped_column(Integer, nullable=False)
    founder_id: Mapped[int] = mapped_column(Integer, nullable=False)
    root_cause_id: Mapped[int] = mapped_column(Integer, nullable=False)
    final_weighted_score: Mapped[decimal.Decimal] = mapped_column(Numeric(6, 4), nullable=False)
    is_top_finding: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text('false'))
    created_at: Mapped[datetime.datetime] = mapped_column(DateTime(True), nullable=False, server_default=text('now()'))
    category_risk_score: Mapped[Optional[decimal.Decimal]] = mapped_column(Numeric(5, 4))
    confirmation_status: Mapped[Optional[str]] = mapped_column(String(15))
    confirmation_multiplier: Mapped[Optional[decimal.Decimal]] = mapped_column(Numeric(3, 2))
    stage_probability: Mapped[Optional[decimal.Decimal]] = mapped_column(Numeric(5, 4))
    industry_probability: Mapped[Optional[decimal.Decimal]] = mapped_column(Numeric(5, 4))
    rank: Mapped[Optional[int]] = mapped_column(Integer)

    founder: Mapped['Founders'] = relationship('Founders', back_populates='detected_root_causes')
    root_cause: Mapped['RootCauses'] = relationship('RootCauses', back_populates='detected_root_causes')
    session: Mapped['Sessions'] = relationship('Sessions', back_populates='detected_root_causes')


class FounderReports(Base):
    __tablename__ = 'founder_reports'
    __table_args__ = (
        CheckConstraint("report_type::text = ANY (ARRAY['full_diagnosis'::character varying, 'founder_dna'::character varying, 'business_dna'::character varying]::text[])", name='founder_reports_report_type_check'),
        ForeignKeyConstraint(['founder_id'], ['founders.founder_id'], ondelete='CASCADE', name='founder_reports_founder_id_fkey'),
        ForeignKeyConstraint(['session_id'], ['sessions.session_id'], ondelete='CASCADE', name='founder_reports_session_id_fkey'),
        PrimaryKeyConstraint('report_id', name='founder_reports_pkey'),
        Index('idx_founder_reports_founder', 'founder_id'),
        Index('idx_founder_reports_session', 'session_id'),
    )

    report_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    founder_id: Mapped[int] = mapped_column(Integer, nullable=False)
    session_id: Mapped[int] = mapped_column(Integer, nullable=False)
    report_type: Mapped[str] = mapped_column(String(30), nullable=False, server_default=text("'full_diagnosis'::character varying"))
    distress_acknowledged_first: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text('false'))
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text('true'))
    generated_at: Mapped[datetime.datetime] = mapped_column(DateTime(True), nullable=False, server_default=text('now()'))
    created_at: Mapped[datetime.datetime] = mapped_column(DateTime(True), nullable=False, server_default=text('now()'))
    updated_at: Mapped[datetime.datetime] = mapped_column(DateTime(True), nullable=False, server_default=text('now()'))
    confirm_actions: Mapped[dict] = mapped_column(JSONB, nullable=False, server_default=text("'[]'::jsonb"))
    solve_actions: Mapped[dict] = mapped_column(JSONB, nullable=False, server_default=text("'[]'::jsonb"))
    title: Mapped[Optional[str]] = mapped_column(String(255))
    summary: Mapped[Optional[str]] = mapped_column(Text)
    founder_dna: Mapped[Optional[dict]] = mapped_column(JSONB)
    business_dna: Mapped[Optional[dict]] = mapped_column(JSONB)
    insights: Mapped[Optional[dict]] = mapped_column(JSONB, server_default=text("'[]'::jsonb"))
    top_root_cause_ids: Mapped[Optional[dict]] = mapped_column(JSONB, server_default=text("'[]'::jsonb"))
    recommended_intervention_ids: Mapped[Optional[dict]] = mapped_column(JSONB, server_default=text("'[]'::jsonb"))
    session_state_at_generation: Mapped[Optional[str]] = mapped_column(String(30))

    founder: Mapped['Founders'] = relationship('Founders', back_populates='founder_reports')
    session: Mapped['Sessions'] = relationship('Sessions', back_populates='founder_reports')
    founder_feedback: Mapped[list['FounderFeedback']] = relationship('FounderFeedback', back_populates='report')
    internal_intelligence_reports: Mapped[list['InternalIntelligenceReports']] = relationship('InternalIntelligenceReports', back_populates='report')


class RagRetrievalLog(Base):
    __tablename__ = 'rag_retrieval_log'
    __table_args__ = (
        ForeignKeyConstraint(['conversation_id'], ['conversations.conversation_id'], ondelete='SET NULL', name='rag_retrieval_log_conversation_id_fkey'),
        ForeignKeyConstraint(['founder_id'], ['founders.founder_id'], ondelete='CASCADE', name='rag_retrieval_log_founder_id_fkey'),
        ForeignKeyConstraint(['session_id'], ['sessions.session_id'], ondelete='SET NULL', name='rag_retrieval_log_session_id_fkey'),
        PrimaryKeyConstraint('log_id', name='rag_retrieval_log_pkey'),
        Index('idx_rag_log_conversation', 'conversation_id'),
        Index('idx_rag_log_founder', 'founder_id'),
        Index('idx_rag_log_session', 'session_id'),
    )

    log_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    query_text: Mapped[str] = mapped_column(Text, nullable=False)
    retrieved_table: Mapped[str] = mapped_column(String(50), nullable=False)
    retrieved_ids: Mapped[dict] = mapped_column(JSONB, nullable=False, server_default=text("'[]'::jsonb"))
    similarity_scores: Mapped[dict] = mapped_column(JSONB, nullable=False, server_default=text("'[]'::jsonb"))
    created_at: Mapped[datetime.datetime] = mapped_column(DateTime(True), nullable=False, server_default=text('now()'))
    founder_id: Mapped[Optional[int]] = mapped_column(Integer)
    session_id: Mapped[Optional[int]] = mapped_column(Integer)
    conversation_id: Mapped[Optional[int]] = mapped_column(Integer)
    message_id: Mapped[Optional[int]] = mapped_column(Integer)
    top_result_id: Mapped[Optional[int]] = mapped_column(Integer)
    top_similarity_score: Mapped[Optional[decimal.Decimal]] = mapped_column(Numeric(5, 4))

    conversation: Mapped[Optional['Conversations']] = relationship('Conversations', back_populates='rag_retrieval_log')
    founder: Mapped[Optional['Founders']] = relationship('Founders', back_populates='rag_retrieval_log')
    session: Mapped[Optional['Sessions']] = relationship('Sessions', back_populates='rag_retrieval_log')


class StageAssessments(Base):
    __tablename__ = 'stage_assessments'
    __table_args__ = (
        ForeignKeyConstraint(['founder_id'], ['founders.founder_id'], ondelete='CASCADE', name='stage_assessments_founder_id_fkey'),
        ForeignKeyConstraint(['session_id'], ['sessions.session_id'], ondelete='SET NULL', name='stage_assessments_session_id_fkey'),
        ForeignKeyConstraint(['stage_id'], ['founder_stages.stage_id'], name='stage_assessments_stage_id_fkey'),
        PrimaryKeyConstraint('assessment_id', name='stage_assessments_pkey'),
        Index('idx_stage_assessments_current', 'founder_id', postgresql_where='(is_current = true)'),
        Index('idx_stage_assessments_founder', 'founder_id'),
    )

    assessment_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    founder_id: Mapped[int] = mapped_column(Integer, nullable=False)
    stage_id: Mapped[int] = mapped_column(Integer, nullable=False)
    is_current: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text('true'))
    assessed_at: Mapped[datetime.datetime] = mapped_column(DateTime(True), nullable=False, server_default=text('now()'))
    created_at: Mapped[datetime.datetime] = mapped_column(DateTime(True), nullable=False, server_default=text('now()'))
    session_id: Mapped[Optional[int]] = mapped_column(Integer)
    confidence_score: Mapped[Optional[decimal.Decimal]] = mapped_column(Numeric(4, 2))
    assessment_basis: Mapped[Optional[str]] = mapped_column(Text)

    founder: Mapped['Founders'] = relationship('Founders', back_populates='stage_assessments')
    session: Mapped[Optional['Sessions']] = relationship('Sessions', back_populates='stage_assessments')
    stage: Mapped['FounderStages'] = relationship('FounderStages', back_populates='stage_assessments')


class FounderFeedback(Base):
    __tablename__ = 'founder_feedback'
    __table_args__ = (
        CheckConstraint("feedback_type::text = ANY (ARRAY['report_rating'::character varying, 'recommendation_helpful'::character varying, 'outcome_30day'::character varying, 'outcome_60day'::character varying, 'outcome_90day'::character varying, 'general'::character varying]::text[])", name='founder_feedback_feedback_type_check'),
        CheckConstraint('rating >= 1 AND rating <= 5', name='founder_feedback_rating_check'),
        ForeignKeyConstraint(['founder_id'], ['founders.founder_id'], ondelete='CASCADE', name='founder_feedback_founder_id_fkey'),
        ForeignKeyConstraint(['intervention_id'], ['interventions.intervention_id'], name='founder_feedback_intervention_id_fkey'),
        ForeignKeyConstraint(['report_id'], ['founder_reports.report_id'], ondelete='SET NULL', name='founder_feedback_report_id_fkey'),
        ForeignKeyConstraint(['session_id'], ['sessions.session_id'], ondelete='SET NULL', name='founder_feedback_session_id_fkey'),
        PrimaryKeyConstraint('feedback_id', name='founder_feedback_pkey'),
        Index('idx_founder_feedback_founder', 'founder_id'),
        Index('idx_founder_feedback_type', 'feedback_type'),
    )

    feedback_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    founder_id: Mapped[int] = mapped_column(Integer, nullable=False)
    feedback_type: Mapped[str] = mapped_column(String(30), nullable=False)
    collected_at: Mapped[datetime.datetime] = mapped_column(DateTime(True), nullable=False, server_default=text('now()'))
    created_at: Mapped[datetime.datetime] = mapped_column(DateTime(True), nullable=False, server_default=text('now()'))
    session_id: Mapped[Optional[int]] = mapped_column(Integer)
    report_id: Mapped[Optional[int]] = mapped_column(Integer)
    intervention_id: Mapped[Optional[int]] = mapped_column(Integer)
    rating: Mapped[Optional[int]] = mapped_column(Integer)
    outcome_text: Mapped[Optional[str]] = mapped_column(Text)
    outcome_metrics: Mapped[Optional[dict]] = mapped_column(JSONB, server_default=text("'{}'::jsonb"))

    founder: Mapped['Founders'] = relationship('Founders', back_populates='founder_feedback')
    intervention: Mapped[Optional['Interventions']] = relationship('Interventions', back_populates='founder_feedback')
    report: Mapped[Optional['FounderReports']] = relationship('FounderReports', back_populates='founder_feedback')
    session: Mapped[Optional['Sessions']] = relationship('Sessions', back_populates='founder_feedback')


class InternalIntelligenceReports(Base):
    __tablename__ = 'internal_intelligence_reports'
    __table_args__ = (
        CheckConstraint("psychological_state::text = ANY (ARRAY['stable'::character varying, 'significantly_guarded'::character varying, 'high_distress'::character varying]::text[])", name='internal_intelligence_reports_psychological_state_check'),
        ForeignKeyConstraint(['founder_id'], ['founders.founder_id'], ondelete='CASCADE', name='internal_intelligence_reports_founder_id_fkey'),
        ForeignKeyConstraint(['report_id'], ['founder_reports.report_id'], ondelete='SET NULL', name='internal_intelligence_reports_report_id_fkey'),
        ForeignKeyConstraint(['session_id'], ['sessions.session_id'], ondelete='CASCADE', name='internal_intelligence_reports_session_id_fkey'),
        PrimaryKeyConstraint('internal_report_id', name='internal_intelligence_reports_pkey'),
        Index('idx_internal_reports_flagged', 'founder_id', postgresql_where='(flagged_for_review = true)'),
        Index('idx_internal_reports_founder', 'founder_id'),
    )

    internal_report_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    founder_id: Mapped[int] = mapped_column(Integer, nullable=False)
    session_id: Mapped[int] = mapped_column(Integer, nullable=False)
    flagged_for_review: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text('false'))
    created_at: Mapped[datetime.datetime] = mapped_column(DateTime(True), nullable=False, server_default=text('now()'))
    updated_at: Mapped[datetime.datetime] = mapped_column(DateTime(True), nullable=False, server_default=text('now()'))
    report_id: Mapped[Optional[int]] = mapped_column(Integer)
    psychological_state: Mapped[Optional[str]] = mapped_column(String(30))
    distress_signals: Mapped[Optional[dict]] = mapped_column(JSONB, server_default=text("'[]'::jsonb"))
    internal_notes: Mapped[Optional[str]] = mapped_column(Text)
    blind_spot_ids: Mapped[Optional[dict]] = mapped_column(JSONB, server_default=text("'[]'::jsonb"))
    behaviour_pattern_ids: Mapped[Optional[dict]] = mapped_column(JSONB, server_default=text("'[]'::jsonb"))
    reviewed_by: Mapped[Optional[str]] = mapped_column(String(100))
    reviewed_at: Mapped[Optional[datetime.datetime]] = mapped_column(DateTime(True))

    founder: Mapped['Founders'] = relationship('Founders', back_populates='internal_intelligence_reports')
    report: Mapped[Optional['FounderReports']] = relationship('FounderReports', back_populates='internal_intelligence_reports')
    session: Mapped['Sessions'] = relationship('Sessions', back_populates='internal_intelligence_reports')

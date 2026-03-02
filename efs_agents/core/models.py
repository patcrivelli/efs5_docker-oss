import os
import uuid
from django.db import models
from pgvector.django import VectorField, HnswIndex

# Match your embedding model dimension; override with AGENTS_EMBED_DIM if needed.
EMBED_DIM = int(os.getenv("AGENTS_EMBED_DIM", 1536))


class AgentSectionData(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    bot_name = models.CharField(max_length=255, null=True, blank=True, help_text="Name of the bot")
    created_by = models.CharField(max_length=100, default='admin', help_text="User who created the bot")
    date_created = models.DateTimeField(auto_now_add=True, help_text="Date the bot was created")

    # Create Agent tab
    business_function = models.CharField(max_length=255, null=True, blank=True)
    persona = models.TextField(null=True, blank=True)
    selected_models = models.JSONField(null=True, blank=True)

    # (Optional) vector of the persona text for retrieval
    persona_embedding = VectorField(dimensions=EMBED_DIM, null=True, blank=True)

    # Placeholder for future sections
    agent_archive = models.JSONField(null=True, blank=True)
    memory_studio = models.JSONField(null=True, blank=True)

    memory_config = models.ForeignKey(
        "MemoryConfiguration",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="agents",
    )


    class Meta:
        db_table = "agent_section_data"
        indexes = [
            HnswIndex(
                fields=["persona_embedding"],
                name="agent_persona_hnsw_cosine",
                opclasses=["vector_cosine_ops"],   # ✅ fixed
                m=16,
                ef_construction=64,
            ),
        ]

    def __str__(self):
        return self.bot_name or f"AgentSectionData {self.id}"


class MemoryConfiguration(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    config_name = models.CharField(max_length=200, default="Default Memory Config")
    description = models.TextField(blank=True, null=True)

    # --- STM ---
    stm_max_tokens = models.IntegerField(default=8000)

    attention_user_focus = models.BooleanField(default=False)
    attention_recent_inputs = models.BooleanField(default=False)
    attention_recurring_topics = models.BooleanField(default=False)
    attention_custom_focus_rules = models.TextField(blank=True, null=True)

    token_management_strategy = models.CharField(
        max_length=50,
        choices=[("preserve", "Preserve"), ("compress", "Compress"), ("summarize", "Summarize")],
        default="preserve"
    )
    critical_keywords = models.TextField(blank=True, null=True)
    overflow_policy = models.CharField(
        max_length=50,
        choices=[("discard_oldest", "Discard Oldest"), ("transfer_to_ltm", "Transfer to LTM"), ("compress_context", "Compress Context")],
        default="discard_oldest"
    )

    episodic_conversation_history = models.BooleanField(default=False)
    episodic_user_preferences = models.BooleanField(default=False)
    episodic_user_behavior = models.BooleanField(default=False)
    episodic_retention_duration = models.CharField(
        max_length=50,
        choices=[("session", "This Session Only"), ("7d", "7 Days"), ("30d", "30 Days"), ("forever", "Forever")],
        default="session"
    )

    # --- LTM ---
    framework = models.CharField(
        max_length=50,
        choices=[("langchain", "Langchain"), ("llamaindex", "LlamaIndex"), ("custom", "Custom")],
        default="langchain"
    )

    semantic_enabled = models.BooleanField(default=False)
    semantic_compliance_data = models.BooleanField(default=False)

    procedural_enabled = models.BooleanField(default=False)
    procedural_strict_workflows = models.BooleanField(default=False)

    ltm_relevance_threshold = models.FloatField(default=0.7)
    ltm_enable_rag = models.BooleanField(default=False)

    consolidation_importance_based = models.BooleanField(default=False)
    consolidation_frequency_based = models.BooleanField(default=False)
    consolidation_explicit_commands = models.BooleanField(default=False)
    decay_period_days = models.IntegerField(default=7)

    # --- Feedback Loops ---
    feedback_explicit = models.BooleanField(default=False)
    feedback_implicit = models.BooleanField(default=False)

    adapt_decay_unused = models.BooleanField(default=False)
    adapt_reinforce_frequent = models.BooleanField(default=False)
    adapt_request_clarification = models.BooleanField(default=False)

    integrate_pre_response = models.BooleanField(default=False)
    integrate_mid_reasoning = models.BooleanField(default=False)
    integrate_post_response = models.BooleanField(default=False)

    # Metadata
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        db_table = "memory_configuration"

    def __str__(self):
        return f"{self.config_name}"


class SemanticMemory(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    config = models.ForeignKey(
        MemoryConfiguration,
        on_delete=models.CASCADE,
        related_name='semantic_memories',
        null=True,
        blank=True
    )
    agent = models.ForeignKey(
        'AgentSectionData',
        on_delete=models.CASCADE,
        related_name='semantic_memories',
        null=True,
        blank=True
    )
    category = models.CharField(max_length=100)
    key = models.CharField(max_length=200)
    value = models.TextField()
    metadata = models.JSONField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField(null=True, blank=True)

    # Vector fields (use one or both; value typically enough)
    key_embedding = VectorField(dimensions=EMBED_DIM, null=True, blank=True)
    value_embedding = VectorField(dimensions=EMBED_DIM, null=True, blank=True)

    class Meta:
        db_table = "semantic_memory"
        indexes = [
            HnswIndex(fields=["value_embedding"], name="sem_value_hnsw_cosine",
                      opclasses=["vector_cosine_ops"], m=16, ef_construction=64),   # ✅ fixed
            HnswIndex(fields=["key_embedding"], name="sem_key_hnsw_cosine",
                      opclasses=["vector_cosine_ops"], m=16, ef_construction=64),   # ✅ fixed
        ]

    def __str__(self):
        if self.agent:
            return f"{self.agent.bot_name} - {self.category}:{self.key}"
        return f"(No Agent) - {self.category}:{self.key}"


class ProceduralMemory(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    config = models.ForeignKey(
        MemoryConfiguration,
        on_delete=models.CASCADE,
        related_name='procedural_memories',
        null=True,
        blank=True
    )
    agent = models.ForeignKey(
        'AgentSectionData',
        on_delete=models.CASCADE,
        related_name='procedural_memories',
        null=True,
        blank=True
    )
    rule_name = models.CharField(max_length=255)
    rule_type = models.CharField(max_length=50)  # knockout / conditional / advisory
    condition_expression = models.TextField()
    action = models.CharField(max_length=1000000)
    metadata = models.JSONField(null=True, blank=True)

    # Embedding over (rule_name + condition + action) for retrieval
    embedding = VectorField(dimensions=EMBED_DIM, null=True, blank=True)

    class Meta:
        db_table = "procedural_memory"
        indexes = [
            HnswIndex(fields=["embedding"], name="proc_rule_hnsw_cosine",
                      opclasses=["vector_cosine_ops"], m=16, ef_construction=64),   # ✅ fixed
        ]

    def __str__(self):
        if self.agent:
            return f"Rule: {self.rule_name} ({self.agent.bot_name})"
        return f"Rule: {self.rule_name} (No Agent)"


class AgentSession(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    agent = models.ForeignKey(AgentSectionData, on_delete=models.CASCADE, related_name='sessions')
    user_id = models.CharField(max_length=255, null=True, blank=True)
    started_at = models.DateTimeField(auto_now_add=True)
    ended_at = models.DateTimeField(null=True, blank=True)
    context_tokens = models.IntegerField(default=0)
    overflow_policy = models.CharField(max_length=50, default='discard_oldest')

    class Meta:
        db_table = "agent_session"

    def __str__(self):
        return f"Session {self.id} ({self.agent.bot_name})"


class EpisodicMemory(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    session = models.ForeignKey(AgentSession, on_delete=models.CASCADE, related_name='episodic_memories')
    timestamp = models.DateTimeField(auto_now_add=True)
    type = models.CharField(max_length=50)  # 'preference', 'correction', 'history', etc.
    content = models.TextField()
    is_promoted = models.BooleanField(default=False)

    # Embed the snippet so you can retrieve similar episodes
    embedding = VectorField(dimensions=EMBED_DIM, null=True, blank=True)

    class Meta:
        db_table = "episodic_memory"
        indexes = [
            HnswIndex(fields=["embedding"], name="episodic_hnsw_cosine",
                      opclasses=["vector_cosine_ops"], m=16, ef_construction=64),   # ✅ fixed
        ]

    def __str__(self):
        return f"Episodic ({self.type}) - {self.timestamp}"


class FeedbackMemory(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    config = models.ForeignKey(
        MemoryConfiguration,
        on_delete=models.CASCADE,
        related_name='feedback_memories',
        null=True,
        blank=True
    )
    agent = models.ForeignKey(
        'AgentSectionData',
        on_delete=models.CASCADE,
        related_name='feedback_memories',
        null=True,
        blank=True
    )
    related_entity = models.CharField(max_length=255)  # e.g., debtor ID or deal ID
    feedback_type = models.CharField(max_length=50)    # 'explicit', 'implicit'
    content = models.TextField()
    action_taken = models.CharField(max_length=255, null=True, blank=True)
    timestamp = models.DateTimeField(auto_now_add=True)

    # Embed the content for retrieval
    embedding = VectorField(dimensions=EMBED_DIM, null=True, blank=True)

    class Meta:
        db_table = "feedback_memory"
        indexes = [
            HnswIndex(fields=["embedding"], name="feedback_hnsw_cosine",
                      opclasses=["vector_cosine_ops"], m=16, ef_construction=64),   # ✅ fixed
        ]

    def __str__(self):
        if self.agent:
            return f"Feedback ({self.feedback_type}) - {self.agent.bot_name}"
        return f"Feedback ({self.feedback_type}) - (No Agent)"



from django.shortcuts import render
from .models import AgentSectionData

def agent_archive(request):
    agents = AgentSectionData.objects.all().order_by("-date_created")
    memory_configs = AgentSectionData.objects.exclude(memory_studio=None)
    return render(request, "efs_agents/agents.html", {
        "agents": agents,
        "memory_configs": memory_configs,
        "selected_originator": None,
        "available_models": [],
    })



# OPTIONAL: unified vector table for cross-type search
class AgentMemoryVector(models.Model):
    """
    Denormalized vector index across memory types for fast, single-table retrieval.
    You can mirror rows from Semantic/Procedural/Episodic/Feedback/Persona here.
    """
    TYPE_CHOICES = [
        ("persona", "Persona"),
        ("semantic", "Semantic"),
        ("procedural", "Procedural"),
        ("episodic", "Episodic"),
        ("feedback", "Feedback"),
        ("other", "Other"),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    agent = models.ForeignKey(AgentSectionData, on_delete=models.CASCADE, related_name="memory_vectors")
    memory_type = models.CharField(max_length=20, choices=TYPE_CHOICES, default="other")

    # Pointer to the source record (keep it generic to avoid tight coupling)
    source_table = models.CharField(max_length=64, null=True, blank=True)
    source_pk = models.UUIDField(null=True, blank=True)

    content = models.TextField()  # the text you embedded
    embedding = VectorField(dimensions=EMBED_DIM)

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "agent_memory_vector"
        indexes = [
            HnswIndex(fields=["embedding"], name="amv_hnsw_cosine",
                      opclasses=["vector_cosine_ops"], m=16, ef_construction=64),   # ✅ fixed
        ]

    def __str__(self):
        return f"{self.memory_type} vector for {self.agent.bot_name}"


# models.py
import os
import uuid
from django.db import models
from pgvector.django import VectorField, HnswIndex
from django.utils import timezone

# ✅ match what your Gemini embedding model returns (very commonly 768)
EMBED_DIM = int(os.getenv("AGENTS_EMBED_DIM", "768"))

class AgentTurnMemory(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    agent = models.ForeignKey(
        "AgentSectionData",
        on_delete=models.CASCADE,
        related_name="turn_memories",
    )

    # "stm" or "ltm"
    tier = models.CharField(max_length=16, default="stm", db_index=True)

    kind = models.CharField(max_length=64, blank=True, default="", db_index=True)
    ticket_label = models.CharField(max_length=255, blank=True, default="")
    abn = models.CharField(max_length=32, blank=True, default="", db_index=True)
    transaction_id = models.CharField(max_length=64, blank=True, default="", db_index=True)

    input_text = models.TextField(blank=True, default="")
    output_text = models.TextField(blank=True, default="")
    compressed_text = models.TextField(blank=True, default="")

    metadata = models.JSONField(default=dict, blank=True)

    # ✅ store vectors on the model
    # You only NEED one of these. If you keep both, ensure your save code writes to both.
    embedding = VectorField(dimensions=EMBED_DIM, null=True, blank=True)
    output_embedding = VectorField(dimensions=EMBED_DIM, null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        indexes = [
            models.Index(fields=["agent", "tier", "created_at"]),
            models.Index(fields=["agent", "transaction_id", "created_at"]),
            models.Index(fields=["agent", "abn", "created_at"]),
            # ✅ HNSW index for similarity search (pick ONE vector field)
            HnswIndex(
                name="agentturnmem_output_emb_hnsw",
                fields=["output_embedding"],  # or ["embedding"] if you only keep embedding
                m=16,
                ef_construction=64,
            ),
        ]
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.agent_id} {self.tier} {self.kind} {self.created_at:%Y-%m-%d %H:%M}"
    """
    STM + LTM memory store.
    - tier='stm': full input/output
    - tier='ltm': compressed output (and usually blank input)
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    agent = models.ForeignKey(AgentSectionData, on_delete=models.CASCADE, related_name="turn_memories")

    tier = models.CharField(max_length=10, default="stm", db_index=True)  # "stm" | "ltm"

    kind = models.CharField(max_length=64, default="general", db_index=True)
    ticket_label = models.CharField(max_length=255, default="Saved Report", db_index=True)

    abn = models.CharField(max_length=11, blank=True, default="", db_index=True)
    transaction_id = models.CharField(max_length=64, blank=True, default="", db_index=True)

    input_text = models.TextField(blank=True, default="")
    output_text = models.TextField(blank=True, default="")

    metadata = models.JSONField(default=dict, blank=True)

    # Vector embedding for semantic retrieval (optional)
    embedding = VectorField(dimensions=EMBED_DIM, null=True, blank=True)

    created_at = models.DateTimeField(default=timezone.now, db_index=True)

    class Meta:
        indexes = [
            models.Index(fields=["agent", "tier", "-created_at"]),
            models.Index(fields=["agent", "kind", "-created_at"]),
            models.Index(fields=["agent", "abn", "-created_at"]),
            models.Index(fields=["agent", "transaction_id", "-created_at"]),
            HnswIndex(
                name="agentturnmemory_embedding_hnsw",
                fields=["embedding"],
                m=16,
                ef_construction=64,
                opclasses=["vector_cosine_ops"],
            ),
        ]

    def __str__(self):
        return f"{self.agent_id} {self.tier} {self.kind} {self.ticket_label} {self.created_at:%Y-%m-%d %H:%M}"
    """
    Stores BOTH:
    - raw text (input/output) for audit + display
    - embedding vector for similarity search
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    agent = models.ForeignKey(
        AgentSectionData,
        on_delete=models.CASCADE,
        related_name="turn_memory",
    )

    kind = models.CharField(max_length=80, default="general", db_index=True)
    ticket_label = models.CharField(max_length=255, default="", blank=True)

    abn = models.CharField(max_length=32, default="", blank=True, db_index=True)
    transaction_id = models.CharField(max_length=64, default="", blank=True, db_index=True)

    input_text = models.TextField(default="", blank=True)
    output_text = models.TextField(default="", blank=True)

    metadata = models.JSONField(default=dict, blank=True)

    # Store embedding for similarity search (nullable so saves work without embeddings configured)
    output_embedding = VectorField(dimensions=EMBED_DIM, null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        indexes = [
            models.Index(fields=["agent", "created_at"]),
            models.Index(fields=["abn", "created_at"]),
            models.Index(fields=["transaction_id", "created_at"]),
            HnswIndex(
                name="agent_turn_memory_output_emb_hnsw",
                fields=["output_embedding"],
                m=16,
                ef_construction=64,
            ),
        ]
    TIER_CHOICES = [("stm", "Short Term"), ("ltm", "Long Term")]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    agent = models.ForeignKey("AgentSectionData", on_delete=models.CASCADE, related_name="turn_memories")

    kind = models.CharField(max_length=64)  # "financial", "bank", etc.
    ticket_label = models.CharField(max_length=255, null=True, blank=True)

    abn = models.CharField(max_length=11, null=True, blank=True)
    transaction_id = models.CharField(max_length=64, null=True, blank=True)  # keep as string to avoid UUID parsing issues

    tier = models.CharField(max_length=8, choices=TIER_CHOICES, default="stm")

    # STM stores full I/O. LTM stores compressed only (input/output can be blanked).
    input_text = models.TextField(blank=True, default="")
    output_text = models.TextField(blank=True, default="")
    compressed_text = models.TextField(blank=True, default="")

    metadata = models.JSONField(null=True, blank=True)

    embedding = VectorField(dimensions=EMBED_DIM, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "agent_turn_memory"
        indexes = [
            HnswIndex(fields=["embedding"], name="atm_hnsw_cosine",
                      opclasses=["vector_cosine_ops"], m=16, ef_construction=64),
        ]
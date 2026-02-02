"""
003_mcq_and_hints.py

MCQ and Hint System Migration

Revision ID: 003
Revises: 002
Create Date: 2026-02-02 07:30:00.000000

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "003"
down_revision: Union[str, None] = "002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Create MCQ and Hint System tables."""
    
    # MCQ Challenges table
    op.create_table(
        "mcq_challenges",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "challenge_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("challenges.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("allow_multiple_answers", sa.Boolean(), default=False),
        sa.Column("shuffle_options", sa.Boolean(), default=True),
        sa.Column("show_correct_after_submit", sa.Boolean(), default=False),
        sa.Column("max_attempts", sa.Integer(), default=3),
        sa.Column("time_limit_seconds", sa.Integer(), nullable=True),
        sa.Column("points_per_question", sa.Numeric(10, 2), default=0),
        sa.Column("penalty_per_wrong", sa.Numeric(10, 2), default=0),
        sa.Column("partial_credit", sa.Boolean(), default=False),
        sa.Column("passing_percentage", sa.Numeric(5, 2), default=70.00),
        sa.Column(
            "created_at",
            sa.TIMESTAMP(timezone=True),
            server_default=sa.text("NOW()"),
        ),
        sa.Column(
            "updated_at",
            sa.TIMESTAMP(timezone=True),
            server_default=sa.text("NOW()"),
            onupdate=sa.text("NOW()"),
        ),
    )
    
    # MCQ Questions table
    op.create_table(
        "mcq_questions",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column(
            "challenge_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("mcq_challenges.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("question_text", sa.Text(), nullable=False),
        sa.Column(
            "question_type",
            sa.String(20),
            sa.CheckConstraint("question_type IN ('single', 'multiple', 'true_false')"),
            default="single",
        ),
        sa.Column("explanation", sa.Text(), nullable=True),
        sa.Column("difficulty_weight", sa.Numeric(3, 2), default=1.00),
        sa.Column("order_index", sa.Integer(), default=0),
        sa.Column("image_url", sa.String(255), nullable=True),
        sa.Column("code_snippet", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.TIMESTAMP(timezone=True),
            server_default=sa.text("NOW()"),
        ),
    )
    
    # MCQ Options table
    op.create_table(
        "mcq_options",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column(
            "question_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("mcq_questions.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("option_text", sa.Text(), nullable=False),
        sa.Column("is_correct", sa.Boolean(), default=False),
        sa.Column("explanation", sa.Text(), nullable=True),
        sa.Column("order_index", sa.Integer(), default=0),
    )
    
    # MCQ Attempts table
    op.create_table(
        "mcq_attempts",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column(
            "user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id"),
            nullable=False,
        ),
        sa.Column(
            "challenge_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("mcq_challenges.id"),
            nullable=False,
        ),
        sa.Column(
            "question_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("mcq_questions.id"),
            nullable=False,
        ),
        sa.Column(
            "selected_options",
            postgresql.ARRAY(postgresql.UUID(as_uuid=True)),
            nullable=False,
        ),
        sa.Column("is_correct", sa.Boolean(), nullable=True),
        sa.Column("attempt_number", sa.Integer(), nullable=False),
        sa.Column("time_spent_seconds", sa.Integer(), nullable=True),
        sa.Column("ip_address", postgresql.INET(), nullable=True),
        sa.Column("user_agent", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.TIMESTAMP(timezone=True),
            server_default=sa.text("NOW()"),
        ),
        sa.UniqueConstraint("user_id", "question_id", "attempt_number"),
    )
    
    # Hint Config table
    op.create_table(
        "hint_config",
        sa.Column(
            "challenge_id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
        ),
        sa.Column("enabled", sa.Boolean(), default=True),
        sa.Column(
            "unlock_mode",
            sa.String(20),
            sa.CheckConstraint(
                "unlock_mode IN ('manual', 'timed', 'progressive', 'attempt_based', 'purchase')"
            ),
            default="manual",
        ),
        sa.Column("auto_unlock_minutes", sa.Integer(), nullable=True),
        sa.Column("progressive_chain", sa.Boolean(), default=False),
        sa.Column(
            "deduction_type",
            sa.String(20),
            sa.CheckConstraint(
                "deduction_type IN ('points', 'percentage', 'time_penalty')"
            ),
            default="points",
        ),
        sa.Column("deduction_value", sa.Numeric(10, 2), default=10.00),
        sa.Column("max_hints_visible", sa.Integer(), nullable=True),
        sa.Column("cooldown_seconds", sa.Integer(), default=0),
        sa.Column(
            "updated_at",
            sa.TIMESTAMP(timezone=True),
            server_default=sa.text("NOW()"),
            onupdate=sa.text("NOW()"),
        ),
        sa.ForeignKeyConstraint(
            ["challenge_id"],
            ["challenges.id"],
            ondelete="CASCADE",
        ),
    )
    
    # Hints table
    op.create_table(
        "hints",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column(
            "challenge_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("challenges.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("title", sa.String(200), nullable=True),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("content_type", sa.String(20), default="text"),
        sa.Column("attachment_url", sa.String(255), nullable=True),
        sa.Column("sequence_order", sa.Integer(), default=0),
        sa.Column("unlock_after_minutes", sa.Integer(), nullable=True),
        sa.Column("unlock_after_attempts", sa.Integer(), nullable=True),
        sa.Column(
            "unlock_after_hint_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("hints.id"),
            nullable=True,
        ),
        sa.Column("custom_cost", sa.Numeric(10, 2), nullable=True),
        sa.Column(
            "created_at",
            sa.TIMESTAMP(timezone=True),
            server_default=sa.text("NOW()"),
        ),
    )
    
    # User Hints table (tracks unlocked hints)
    op.create_table(
        "user_hints",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column(
            "user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id"),
            nullable=False,
        ),
        sa.Column(
            "hint_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("hints.id"),
            nullable=False,
        ),
        sa.Column(
            "challenge_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("challenges.id"),
            nullable=False,
        ),
        sa.Column(
            "unlocked_at",
            sa.TIMESTAMP(timezone=True),
            server_default=sa.text("NOW()"),
        ),
        sa.Column("points_deducted", sa.Numeric(10, 2), default=0),
        sa.Column("time_into_challenge", sa.Interval(), nullable=True),
        sa.Column("attempt_number_when_used", sa.Integer(), nullable=True),
        sa.UniqueConstraint("user_id", "hint_id"),
    )
    
    # Create indexes for performance
    op.create_index(
        "idx_mcq_attempts_user_challenge",
        "mcq_attempts",
        ["user_id", "challenge_id"],
    )
    op.create_index(
        "idx_mcq_questions_challenge",
        "mcq_questions",
        ["challenge_id", "order_index"],
    )
    op.create_index(
        "idx_mcq_options_question",
        "mcq_options",
        ["question_id", "order_index"],
    )
    op.create_index(
        "idx_hints_challenge",
        "hints",
        ["challenge_id", "sequence_order"],
    )
    op.create_index(
        "idx_user_hints_user",
        "user_hints",
        ["user_id", "challenge_id"],
    )
    
    # Create function to prevent hint usage after challenge solved
    op.execute("""
        CREATE OR REPLACE FUNCTION check_hint_before_solve()
        RETURNS TRIGGER AS $$
        BEGIN
            IF EXISTS (
                SELECT 1 FROM submissions 
                WHERE user_id = NEW.user_id 
                AND challenge_id = NEW.challenge_id 
                AND is_correct = true
            ) THEN
                RAISE EXCEPTION 'Cannot unlock hint after challenge is solved';
            END IF;
            RETURN NEW;
        END;
        $$ LANGUAGE plpgsql;
    """)
    
    op.execute("""
        CREATE TRIGGER trigger_check_hint_before_solve
        BEFORE INSERT ON user_hints
        FOR EACH ROW
        EXECUTE FUNCTION check_hint_before_solve();
    """)


def downgrade() -> None:
    """Drop MCQ and Hint System tables."""
    
    # Drop trigger and function
    op.execute("DROP TRIGGER IF EXISTS trigger_check_hint_before_solve ON user_hints")
    op.execute("DROP FUNCTION IF EXISTS check_hint_before_solve()")
    
    # Drop indexes
    op.drop_index("idx_user_hints_user", table_name="user_hints")
    op.drop_index("idx_hints_challenge", table_name="hints")
    op.drop_index("idx_mcq_options_question", table_name="mcq_options")
    op.drop_index("idx_mcq_questions_challenge", table_name="mcq_questions")
    op.drop_index("idx_mcq_attempts_user_challenge", table_name="mcq_attempts")
    
    # Drop tables
    op.drop_table("user_hints")
    op.drop_table("hints")
    op.drop_table("hint_config")
    op.drop_table("mcq_attempts")
    op.drop_table("mcq_options")
    op.drop_table("mcq_questions")
    op.drop_table("mcq_challenges")

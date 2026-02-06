"""add_observation_version_and_status

Revision ID: 000000000006
Revises: 000000000005
Create Date: 2026-02-06 00:00:06.000000+00:00

- 为 execution_observations 增加 version 列（代码/模型版本）
- 为已部署且缺少 status 列的环境补上 status 列与 observationstatus 枚举（幂等）
"""

from typing import Sequence, Union

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "000000000006"
down_revision: Union[str, None] = "000000000005"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. 新增 version 列（所有环境）
    op.add_column(
        "execution_observations",
        sa.Column("version", sa.String(50), nullable=True, comment="代码/模型版本"),
    )

    # 2. 若表已存在但无 status 列（先于 status 合并前已执行 000000000005 的环境），补上枚举与列
    conn = op.get_bind()
    if conn.dialect.name == "postgresql":
        # 创建 observationstatus 枚举（若不存在）
        op.execute(
            sa.text("""
                DO $$
                BEGIN
                    IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'observationstatus') THEN
                        CREATE TYPE observationstatus AS ENUM (
                            'RUNNING', 'COMPLETED', 'FAILED', 'INTERRUPTED'
                        );
                    END IF;
                END$$;
            """)
        )
        # 添加 status 列（若不存在）
        op.execute(
            sa.text("""
                ALTER TABLE execution_observations
                ADD COLUMN IF NOT EXISTS status observationstatus
                NOT NULL DEFAULT 'RUNNING'::observationstatus
            """)
        )


def downgrade() -> None:
    op.drop_column("execution_observations", "version")
    # 不自动删除 status 列，避免影响已依赖该列的应用；若需回滚可手动执行：
    # ALTER TABLE execution_observations DROP COLUMN IF EXISTS status;
    # DROP TYPE IF EXISTS observationstatus;

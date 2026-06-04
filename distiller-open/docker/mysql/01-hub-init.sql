-- ============================================================================
-- Hub Core Layer DDL (中枢内核层)
-- Version: 1.0.0
-- Description: 9 张共享 Hub 表 - 跨项目共用的中枢内核
-- Charset: utf8mb4 / Collation: utf8mb4_0900_ai_ci
-- Engine: InnoDB
-- Notes:
--   - approval_gates 不在本层（在 distiller app 层，由 A4 处理）
--   - memories 表已按方案 D 改造：去 tier+confidence，加 memory_type/bi-temporal/trace_id
--   - zone_name 仅做命名空间，非物理隔离
-- ============================================================================

SET NAMES utf8mb4;
SET FOREIGN_KEY_CHECKS = 0;

-- ----------------------------------------------------------------------------
-- 1) projects: 项目注册表（租户/项目维度）
-- ----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS projects (
  project_id VARCHAR(64) NOT NULL COMMENT '项目唯一标识',
  name VARCHAR(255) NOT NULL COMMENT '项目名称',
  description TEXT COMMENT '项目描述',
  status ENUM('active','archived','suspended') NOT NULL DEFAULT 'active' COMMENT '项目状态',
  owner VARCHAR(128) DEFAULT NULL COMMENT '项目 owner',
  metadata JSON DEFAULT NULL COMMENT '扩展元数据',
  created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (project_id),
  KEY idx_projects_status (status),
  KEY idx_projects_updated (updated_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci COMMENT='项目注册表';

-- ----------------------------------------------------------------------------
-- 2) schema_versions: 结构版本表（新增）
-- ----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS schema_versions (
  version VARCHAR(20) NOT NULL COMMENT '语义化版本号',
  applied_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '应用时间',
  description TEXT COMMENT '版本说明',
  migration_file VARCHAR(255) DEFAULT NULL COMMENT '迁移脚本文件名',
  PRIMARY KEY (version)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci COMMENT='结构版本表';

-- ----------------------------------------------------------------------------
-- 3) sessions: 会话记录
-- ----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS sessions (
  session_id VARCHAR(64) NOT NULL COMMENT '会话唯一标识',
  project_id VARCHAR(64) NOT NULL COMMENT '所属项目',
  zone_name VARCHAR(128) DEFAULT NULL COMMENT '命名空间，非物理隔离',
  agent_name VARCHAR(128) DEFAULT NULL COMMENT 'Agent 名称',
  title VARCHAR(512) DEFAULT NULL COMMENT '会话标题',
  status ENUM('open','closed','aborted') NOT NULL DEFAULT 'open' COMMENT '会话状态',
  started_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  ended_at TIMESTAMP NULL DEFAULT NULL,
  metadata JSON DEFAULT NULL,
  PRIMARY KEY (session_id),
  KEY idx_sessions_project (project_id),
  KEY idx_sessions_status (status),
  KEY idx_sessions_started (started_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci COMMENT='会话记录';

-- ----------------------------------------------------------------------------
-- 4) memories: 核心记忆（方案 D 重大改造）
--   - 去掉 tier / confidence
--   - 新增 memory_type / valid_from / valid_to / episode_id / trace_id
--   - 保留 importance / active / superseded_by
-- ----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS memories (
  memory_id BIGINT NOT NULL AUTO_INCREMENT COMMENT '记忆 ID',
  project_id VARCHAR(64) NOT NULL COMMENT '所属项目',
  session_id VARCHAR(64) DEFAULT NULL COMMENT '所属会话（可空）',
  memory_type ENUM(
    'preference',
    'fact',
    'decision',
    'context',
    'reference',
    'acceptance_criteria',
    'verification_result'
  ) NOT NULL COMMENT '记忆类型（取代 tier+confidence）',
  title VARCHAR(512) DEFAULT NULL COMMENT '记忆标题',
  content MEDIUMTEXT NOT NULL COMMENT '记忆内容',
  tags JSON DEFAULT NULL COMMENT '标签数组',
  importance TINYINT NOT NULL DEFAULT 3 COMMENT '重要度 1-5',
  active BOOLEAN NOT NULL DEFAULT TRUE COMMENT '是否活跃',
  superseded_by BIGINT DEFAULT NULL COMMENT '被哪条记忆替代',
  valid_from TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT 'bi-temporal 有效期起',
  valid_to TIMESTAMP NULL DEFAULT NULL COMMENT 'bi-temporal 有效期止（NULL=至今）',
  episode_id BIGINT DEFAULT NULL COMMENT '关联 JSONL episode/offset，跨表外键不强约束',
  trace_id VARCHAR(36) DEFAULT NULL COMMENT '链路追踪 ID',
  created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (memory_id),
  KEY idx_memories_project (project_id),
  KEY idx_memories_session (session_id),
  KEY idx_memories_type (memory_type),
  KEY idx_memories_active (active),
  KEY idx_memories_importance (importance),
  KEY idx_memories_valid (valid_from, valid_to),
  KEY idx_memories_episode (episode_id),
  KEY idx_memories_trace (trace_id),
  FULLTEXT KEY ft_memories_content (title, content) WITH PARSER ngram
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci COMMENT='核心记忆（方案 D）';

-- ----------------------------------------------------------------------------
-- 5) interface_registry: 接口注册表（hub 共享）
-- ----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS interface_registry (
  interface_id VARCHAR(128) NOT NULL COMMENT '接口标识',
  project_id VARCHAR(64) NOT NULL COMMENT '所属项目',
  name VARCHAR(255) NOT NULL COMMENT '接口名',
  signature TEXT COMMENT '签名/契约',
  version VARCHAR(32) NOT NULL DEFAULT '1.0.0' COMMENT '版本',
  status ENUM('draft','active','deprecated','removed') NOT NULL DEFAULT 'draft',
  metadata JSON DEFAULT NULL,
  created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (interface_id),
  KEY idx_iface_project (project_id),
  KEY idx_iface_status (status),
  KEY idx_iface_name (name)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci COMMENT='接口注册表';

-- ----------------------------------------------------------------------------
-- 6) audit_log: 审计日志（新增 trace_id）
-- ----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS audit_log (
  audit_id BIGINT NOT NULL AUTO_INCREMENT COMMENT '审计 ID',
  project_id VARCHAR(64) DEFAULT NULL COMMENT '项目',
  session_id VARCHAR(64) DEFAULT NULL COMMENT '会话',
  actor VARCHAR(128) DEFAULT NULL COMMENT '操作主体',
  action VARCHAR(128) NOT NULL COMMENT '动作',
  target_type VARCHAR(64) DEFAULT NULL COMMENT '目标类型',
  target_id VARCHAR(128) DEFAULT NULL COMMENT '目标 ID',
  payload JSON DEFAULT NULL COMMENT '负载/diff',
  trace_id VARCHAR(36) DEFAULT NULL COMMENT '链路追踪 ID',
  created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (audit_id),
  KEY idx_audit_project (project_id),
  KEY idx_audit_session (session_id),
  KEY idx_audit_action (action),
  KEY idx_audit_trace (trace_id),
  KEY idx_audit_created (created_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci COMMENT='审计日志';

-- ----------------------------------------------------------------------------
-- 7) checkpoints: 检查点
-- ----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS checkpoints (
  checkpoint_id VARCHAR(64) NOT NULL COMMENT '检查点 ID',
  project_id VARCHAR(64) NOT NULL COMMENT '项目',
  session_id VARCHAR(64) DEFAULT NULL COMMENT '会话',
  name VARCHAR(255) DEFAULT NULL COMMENT '检查点名',
  state JSON DEFAULT NULL COMMENT '状态快照',
  description TEXT COMMENT '说明',
  created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (checkpoint_id),
  KEY idx_ckpt_project (project_id),
  KEY idx_ckpt_session (session_id),
  KEY idx_ckpt_created (created_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci COMMENT='检查点';

-- ----------------------------------------------------------------------------
-- 8) sync_watermarks: 同步水位（保留作未来扩展）
-- ----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS sync_watermarks (
  source VARCHAR(128) NOT NULL COMMENT '同步源标识',
  project_id VARCHAR(64) NOT NULL COMMENT '项目',
  watermark VARCHAR(128) NOT NULL COMMENT '水位（offset/timestamp/lsn 等）',
  last_synced_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  metadata JSON DEFAULT NULL,
  PRIMARY KEY (source, project_id),
  KEY idx_sync_project (project_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci COMMENT='同步水位';

-- ----------------------------------------------------------------------------
-- 9) tenants: 租户预留（本期不强制使用）
-- ----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS tenants (
  id VARCHAR(36) NOT NULL,
  name VARCHAR(255) NOT NULL,
  description TEXT,
  active BOOLEAN NOT NULL DEFAULT TRUE,
  created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (id),
  KEY idx_tenants_active (active)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci COMMENT='租户预留';

SET FOREIGN_KEY_CHECKS = 1;

-- ----------------------------------------------------------------------------
-- 初始化版本记录
-- ----------------------------------------------------------------------------
INSERT INTO schema_versions(version, description) VALUES ('1.0.0', 'Hub Core initial DDL');

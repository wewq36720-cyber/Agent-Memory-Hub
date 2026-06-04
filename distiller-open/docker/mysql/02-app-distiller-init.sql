-- ============================================================================
-- Distiller App Layer — 应用层 DDL（业务表）
-- ----------------------------------------------------------------------------
-- 三层架构定位：本文件属于 "App" 层（参见 docs/方案说明.md §2.1）。
--   单 schema 设计：所有表共存于 distiller_hub 数据库
--     Hub 层  : projects / sessions / memories / 等（由 01-hub-init.sql 建立）
--     App 层  : 本文件（distiller 业务表，7 张业务表 + verification_evidence）
--   多 agent 项目共享同一 hub schema，用 project_id 列做租户隔离（方案 D 决策 ARCH-D02）
-- ----------------------------------------------------------------------------
-- 本期相对 v1.0 的变更（DIST-01~10 落地）：
--   1. 全表新增 trace_id VARCHAR(36)         —— 串联跨层日志（DIST-08）
--   2. project_modules 新增 acceptance_schema JSON  —— 可执行验收 JSON Schema（DIST-04）
--   3. review_results 新增 checklist_items JSON     —— 借鉴 Spec Kit Review & Acceptance Checklist
--   4. approval_gates.gate_type ENUM → VARCHAR(50)  —— 避免 ENUM 加值要 ALTER 全表（DIST-09）
--   5. 新增 verification_evidence 表                 —— Evidence Card 落地（§4.1）
--   6. 字符集统一 utf8mb4 / utf8mb4_0900_ai_ci      —— 与 Hub 层一致
-- ----------------------------------------------------------------------------
-- 外键策略：引用本库 projects(id) 全部 ON DELETE RESTRICT，
--          防止删项目时静默清掉 App 层业务数据。
-- 启动顺序依赖：必须先执行 01-hub-init.sql 建立 projects 表，
--             否则本文件外键创建失败。
-- ============================================================================

USE distiller_hub;

-- ----------------------------------------------------------------------------
-- 1) project_modules — 模块拆分 + zone 分配
-- ----------------------------------------------------------------------------
CREATE TABLE project_modules (
    id                  VARCHAR(36) PRIMARY KEY,
    project_id          VARCHAR(64) NOT NULL,
    module_name         VARCHAR(255) NOT NULL,
    zone_name           VARCHAR(255) NOT NULL UNIQUE,
    assigned_agent      VARCHAR(255),
    acceptance_criteria JSON,
    acceptance_schema   JSON COMMENT 'JSON Schema 格式的可执行验收约束（DIST-04）',
    milestone_date      DATE,
    status              ENUM('active','under_review','approved','rejected','merged')
                        NOT NULL DEFAULT 'active',
    trace_id            VARCHAR(36),
    created_at          TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT fk_pm_project
        FOREIGN KEY (project_id) REFERENCES projects(project_id)
        ON DELETE RESTRICT ON UPDATE CASCADE,
    INDEX idx_pm_project (project_id),
    INDEX idx_pm_status  (project_id, status),
    INDEX idx_pm_trace   (trace_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

-- ----------------------------------------------------------------------------
-- 2) zone_progress — 子 agent 进度汇报
-- ----------------------------------------------------------------------------
CREATE TABLE zone_progress (
    id             BIGINT AUTO_INCREMENT PRIMARY KEY,
    zone_name      VARCHAR(255) NOT NULL,
    status         ENUM('in_progress','blocked','completed','idle')
                   NOT NULL DEFAULT 'in_progress',
    current_task   VARCHAR(500),
    completion_pct TINYINT NOT NULL DEFAULT 0,
    blockers       JSON DEFAULT (JSON_ARRAY()),
    next_plan      TEXT,
    reported_by    VARCHAR(255) NOT NULL,
    trace_id       VARCHAR(36),
    report_time    TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT fk_zp_zone
        FOREIGN KEY (zone_name) REFERENCES project_modules(zone_name)
        ON DELETE RESTRICT ON UPDATE CASCADE,
    INDEX idx_zp_zone  (zone_name),
    INDEX idx_zp_time  (zone_name, report_time),
    INDEX idx_zp_trace (trace_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

-- ----------------------------------------------------------------------------
-- 3) issues — 问题/阻碍上报
-- ----------------------------------------------------------------------------
CREATE TABLE issues (
    id                  BIGINT AUTO_INCREMENT PRIMARY KEY,
    zone_name           VARCHAR(255) NOT NULL,
    reported_by         VARCHAR(255) NOT NULL,
    severity            ENUM('blocker','major','minor','question')
                        NOT NULL DEFAULT 'question',
    title               VARCHAR(500) NOT NULL,
    description         TEXT,
    status              ENUM('open','discussing','resolved','closed')
                        NOT NULL DEFAULT 'open',
    supervisor_response TEXT,
    human_notified      BOOLEAN NOT NULL DEFAULT FALSE,
    trace_id            VARCHAR(36),
    created_at          TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    resolved_at         TIMESTAMP NULL,
    CONSTRAINT fk_iss_zone
        FOREIGN KEY (zone_name) REFERENCES project_modules(zone_name)
        ON DELETE RESTRICT ON UPDATE CASCADE,
    INDEX idx_iss_zone     (zone_name),
    INDEX idx_iss_status   (status),
    INDEX idx_iss_severity (severity),
    INDEX idx_iss_trace    (trace_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

-- ----------------------------------------------------------------------------
-- 4) patrol_logs — 主 agent 巡查日志
--    注：summary JSON 性能问题已在 §3 讨论，本期接受不拆 patrol_findings 子表
-- ----------------------------------------------------------------------------
CREATE TABLE patrol_logs (
    id            BIGINT AUTO_INCREMENT PRIMARY KEY,
    project_id    VARCHAR(64) NOT NULL,
    summary       JSON NOT NULL,
    findings      JSON DEFAULT (JSON_ARRAY()),
    prodded_zones JSON DEFAULT (JSON_ARRAY()),
    trace_id      VARCHAR(36),
    patrol_time   TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT fk_pl_project
        FOREIGN KEY (project_id) REFERENCES projects(project_id)
        ON DELETE RESTRICT ON UPDATE CASCADE,
    INDEX idx_pl_project (project_id),
    INDEX idx_pl_time    (patrol_time),
    INDEX idx_pl_trace   (trace_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

-- ----------------------------------------------------------------------------
-- 5) review_requests — 子 agent 提交审核
-- ----------------------------------------------------------------------------
CREATE TABLE review_requests (
    id           BIGINT AUTO_INCREMENT PRIMARY KEY,
    zone_name    VARCHAR(255) NOT NULL,
    requested_by VARCHAR(255) NOT NULL,
    status       ENUM('pending','in_review','approved','rejected')
                 NOT NULL DEFAULT 'pending',
    notes        TEXT,
    trace_id     VARCHAR(36),
    created_at   TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT fk_rr_zone
        FOREIGN KEY (zone_name) REFERENCES project_modules(zone_name)
        ON DELETE RESTRICT ON UPDATE CASCADE,
    INDEX idx_rr_zone   (zone_name),
    INDEX idx_rr_status (status),
    INDEX idx_rr_trace  (trace_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

-- ----------------------------------------------------------------------------
-- 6) review_results — 主 agent 审核结果
-- ----------------------------------------------------------------------------
CREATE TABLE review_results (
    id              BIGINT AUTO_INCREMENT PRIMARY KEY,
    request_id      BIGINT NOT NULL,
    reviewed_by     VARCHAR(255) NOT NULL,
    approved        BOOLEAN NOT NULL,
    issues          JSON DEFAULT (JSON_ARRAY()),
    checklist_items JSON COMMENT '结构化条目（借鉴 Spec Kit Review & Acceptance Checklist）',
    summary         TEXT,
    trace_id        VARCHAR(36),
    reviewed_at     TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT fk_rres_request
        FOREIGN KEY (request_id) REFERENCES review_requests(id)
        ON DELETE RESTRICT ON UPDATE CASCADE,
    INDEX idx_rres_request (request_id),
    INDEX idx_rres_trace   (trace_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

-- ----------------------------------------------------------------------------
-- 7) approval_gates — 人工审批关口
--    gate_type 由 ENUM 改为 VARCHAR(50)（DIST-09 落地）
--    取值约定（应用层校验）：'project_approval' | 'milestone_gate' | 自定义
-- ----------------------------------------------------------------------------
CREATE TABLE approval_gates (
    id              BIGINT AUTO_INCREMENT PRIMARY KEY,
    project_id      VARCHAR(64) NOT NULL,
    gate_type       VARCHAR(50) NOT NULL DEFAULT 'project_approval',
    status          ENUM('pending','approved','rejected')
                    NOT NULL DEFAULT 'pending',
    report_snapshot JSON,
    human_decision  TEXT,
    trace_id        VARCHAR(36),
    decided_at      TIMESTAMP NULL,
    created_at      TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT fk_ag_project
        FOREIGN KEY (project_id) REFERENCES projects(project_id)
        ON DELETE RESTRICT ON UPDATE CASCADE,
    INDEX idx_ag_project (project_id),
    INDEX idx_ag_status  (status),
    INDEX idx_ag_type    (gate_type),
    INDEX idx_ag_trace   (trace_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

-- ----------------------------------------------------------------------------
-- 8) verification_evidence — Evidence Card 持久化（§4.1 落地）
--    每个验证声明（claim）一条记录，含 covered/not_covered/residual_risk/confidence
-- ----------------------------------------------------------------------------
CREATE TABLE verification_evidence (
    id            BIGINT AUTO_INCREMENT PRIMARY KEY,
    project_id    VARCHAR(64) NOT NULL,
    zone_name     VARCHAR(255),
    claim_type    VARCHAR(50) NOT NULL,
    claim_text    TEXT NOT NULL,
    command       TEXT,
    exit_status   VARCHAR(50),
    covered       TEXT,
    not_covered   TEXT,
    residual_risk TEXT,
    confidence    ENUM('A','B','C') NOT NULL,
    trace_id      VARCHAR(36),
    created_at    TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    INDEX idx_ve_project (project_id),
    INDEX idx_ve_trace   (trace_id),
    INDEX idx_ve_created (created_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

-- ----------------------------------------------------------------------------
-- 版本登记
-- ----------------------------------------------------------------------------
INSERT INTO schema_versions(version, description)
VALUES ('1.0.0-app', 'Distiller App initial DDL');

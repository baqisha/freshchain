-- =============================================================
-- 鲜智链 FreshChain 阶段1：数据库建表脚本
-- 使用方法：在 MySQL 中运行本脚本即可自动建库建表
-- =============================================================

-- 重复运行时先关闭外键约束检查，避免"被引用表无法删除"的 3730 错误
SET FOREIGN_KEY_CHECKS = 0;

CREATE DATABASE IF NOT EXISTS freshchain
  DEFAULT CHARACTER SET utf8mb4 COLLATE utf8mb4_general_ci;

USE freshchain;

-- -------------------------------------------------------------
-- 表1：goods 生鲜商品表（消费者查询 / 特惠推荐的数据源）
-- -------------------------------------------------------------
DROP TABLE IF EXISTS goods;
CREATE TABLE goods (
  goods_id        INT UNSIGNED PRIMARY KEY AUTO_INCREMENT COMMENT '商品ID',
  name            VARCHAR(50)  NOT NULL COMMENT '商品名称',
  category        VARCHAR(30)  NOT NULL COMMENT '分类：蔬菜/水果/肉禽/水产/蛋奶/豆制品',
  unit            VARCHAR(10)  NOT NULL COMMENT '计量单位：斤/个/盒',
  price           DECIMAL(8,2) NOT NULL COMMENT '正常单价',
  promo_price     DECIMAL(8,2) DEFAULT NULL COMMENT '当日特惠价，NULL表示今日无特惠',
  stock           INT UNSIGNED NOT NULL DEFAULT 0 COMMENT '当前库存',
  shelf_life_days INT UNSIGNED NOT NULL DEFAULT 3 COMMENT '保质期（天）',
  storage_tip     VARCHAR(120) DEFAULT NULL COMMENT '储存/挑选提示（供RAG检索用）',
  is_promo        TINYINT(1)   NOT NULL DEFAULT 0 COMMENT '是否当日特惠：1是 0否',
  created_at      DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='生鲜商品表';

-- -------------------------------------------------------------
-- 表2：sales_records 销售流水表（数据分析Agent / 补货预测的数据源）
-- 注意：按天记录每个商品的销量，方便做趋势、热销榜、同环比
-- -------------------------------------------------------------
DROP TABLE IF EXISTS sales_records;
CREATE TABLE sales_records (
  record_id   BIGINT UNSIGNED PRIMARY KEY AUTO_INCREMENT COMMENT '流水ID',
  goods_id    INT UNSIGNED NOT NULL COMMENT '商品ID',
  sale_date   DATE         NOT NULL COMMENT '销售日期',
  quantity    INT UNSIGNED NOT NULL COMMENT '当日销量（单位：斤/个/盒）',
  sale_price  DECIMAL(8,2) NOT NULL COMMENT '当日成交单价',
  channel     VARCHAR(10)  NOT NULL DEFAULT '到店' COMMENT '渠道：到店/线上',
  CONSTRAINT fk_sales_goods FOREIGN KEY (goods_id) REFERENCES goods(goods_id),
  INDEX idx_date (sale_date),
  INDEX idx_goods_date (goods_id, sale_date)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='销售流水表';

-- -------------------------------------------------------------
-- 表3：agent_logs Agent调用日志表（调度监控 + 决赛压测指标埋点）
-- latency_ms / retry_count / confidence 是决赛性能对比要用的字段
-- -------------------------------------------------------------
DROP TABLE IF EXISTS agent_logs;
CREATE TABLE agent_logs (
  log_id          BIGINT UNSIGNED PRIMARY KEY AUTO_INCREMENT COMMENT '日志ID',
  agent_name      VARCHAR(30)  NOT NULL COMMENT '执行Agent名称',
  task_type       VARCHAR(30)  NOT NULL COMMENT '任务类型：consumer_query/manager_analysis/restock',
  input_summary   VARCHAR(500) DEFAULT NULL COMMENT '输入摘要',
  output_summary  VARCHAR(500) DEFAULT NULL COMMENT '输出摘要',
  confidence      DECIMAL(4,2) DEFAULT NULL COMMENT '验证Agent置信度0~1',
  retry_count     INT UNSIGNED NOT NULL DEFAULT 0 COMMENT '本次任务重试次数',
  latency_ms      INT UNSIGNED  NOT NULL DEFAULT 0 COMMENT '总耗时毫秒',
  status          VARCHAR(20)  NOT NULL DEFAULT 'success' COMMENT 'success/rejected/failed',
  created_at      DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP,
  INDEX idx_task (task_type, created_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='Agent调用日志表';

-- -------------------------------------------------------------
-- 表4：feedback 用户/管理层反馈表（反馈记忆Agent 的自循环数据源）
-- adopted=1 采纳 / 0 未采纳，用于反向修正 Prompt 与工具选择
-- -------------------------------------------------------------
DROP TABLE IF EXISTS feedback;
CREATE TABLE feedback (
  feedback_id    BIGINT UNSIGNED PRIMARY KEY AUTO_INCREMENT COMMENT '反馈ID',
  user_role     VARCHAR(15)  NOT NULL COMMENT '角色：consumer/manager',
  related_log_id BIGINT UNSIGNED DEFAULT NULL COMMENT '关联的Agent日志ID',
  content       VARCHAR(500) NOT NULL COMMENT '反馈内容',
  adopted       TINYINT(1)   NOT NULL DEFAULT 1 COMMENT '是否采纳建议：1采纳 0未采纳',
  created_at     DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='反馈表';

-- 重新打开外键约束检查
SET FOREIGN_KEY_CHECKS = 1;

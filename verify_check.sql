-- =============================================================
-- 鲜智链 FreshChain 阶段1：数据校验查询（建表灌数后逐条运行检查）
-- =============================================================
USE freshchain;

-- ① 商品总数，应为 20
SELECT COUNT(*) AS 商品总数 FROM goods;

-- ② 今日特惠商品（is_promo=1），用于消费者Agent演示
SELECT name, category, price, promo_price, stock
FROM goods WHERE is_promo = 1 ORDER BY name;

-- ③ 近7天热销榜（数据分析Agent的核心输入）
SELECT g.name, SUM(s.quantity) AS 近7天总销量
FROM sales_records s JOIN goods g ON s.goods_id = g.goods_id
WHERE s.sale_date >= CURDATE() - INTERVAL 7 DAY
GROUP BY g.goods_id
ORDER BY 近7天总销量 DESC;

-- ④ 近7天滞销榜（补货决策Agent的"少进"依据）
SELECT g.name, SUM(s.quantity) AS 近7天总销量
FROM sales_records s JOIN goods g ON s.goods_id = g.goods_id
WHERE s.sale_date >= CURDATE() - INTERVAL 7 DAY
GROUP BY g.goods_id
ORDER BY 近7天总销量 ASC;

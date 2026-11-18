# -*- coding: utf-8 -*-
"""
FreshChain 自定义工具服务（阶段2）
启动：在 E:\\freshchain 目录下运行
    uvicorn main:app --reload --port 8000
测试：浏览器打开 http://127.0.0.1:8000/docs
"""

from datetime import date, timedelta

from fastapi import FastAPI, HTTPException, Query
from pydantic import BaseModel

from db import query, query_one
import orchestrator

from fastapi.middleware.cors import CORSMiddleware

app = FastAPI(
    title="鲜智链 FreshChain 工具服务",
    description="为消费者Agent、数据分析Agent、预测决策Agent、验证Agent提供的数据工具接口",
    version="1.0",
    # 告诉 Dify（运行在 Docker 容器里）：通过宿主机别名访问本服务
    # 容器内 localhost 指向容器自己，必须用 host.docker.internal
    servers=[{"url": "http://host.docker.internal:8000", "description": "宿主机 FastAPI（供 Docker 容器访问）"}],
)

# 允许浏览器 / Dify 前端跨域访问
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class OrchReq(BaseModel):
    query: str


# ============================================================
# 工具1：查商品列表（支持分类筛选、关键词搜索）—— 供消费者Agent
# ============================================================
@app.get("/api/goods", summary="查询商品列表")
def list_goods(
    category: str = Query(None, description="分类：蔬菜/水果/肉禽/水产/蛋奶/豆制品"),
    keyword: str = Query(None, description="商品名关键词，如：鸡蛋"),
):
    sql = "SELECT goods_id, name, category, unit, price, promo_price, stock, shelf_life_days, storage_tip, is_promo FROM goods WHERE 1=1"
    args = []
    if category:
        sql += " AND category = %s"
        args.append(category)
    if keyword:
        sql += " AND name LIKE %s"
        args.append(f"%{keyword}%")
    sql += " ORDER BY goods_id"
    rows = query(sql, tuple(args))
    return {"count": len(rows), "goods": rows}


# ============================================================
# 工具2：今日特惠 —— 供消费者Agent
# ============================================================
@app.get("/api/promo", summary="查询今日特惠商品")
def today_promo():
    rows = query(
        """SELECT goods_id, name, category, unit, price, promo_price, stock
           FROM goods WHERE is_promo = 1 ORDER BY goods_id"""
    )
    return {"promo_count": len(rows), "promo_goods": rows}


# ============================================================
# 工具3：单个商品详情 —— 供消费者Agent
# ============================================================
@app.get("/api/goods/{goods_id}", summary="查询单个商品详情")
def goods_detail(goods_id: int):
    row = query_one(
        "SELECT goods_id, name, category, unit, price, promo_price, stock, shelf_life_days, storage_tip, is_promo FROM goods WHERE goods_id=%s",
        (goods_id,),
    )
    if not row:
        raise HTTPException(status_code=404, detail="商品不存在")
    return row


# ============================================================
# 工具4：近N天热销榜 —— 供数据分析Agent
# ============================================================
@app.get("/api/sales/top", summary="近N天热销榜")
def sales_top(days: int = Query(7, ge=1, le=90), limit: int = Query(10, ge=1, le=50)):
    rows = query(
        """SELECT g.goods_id, g.name, g.category, SUM(s.quantity) AS total_qty,
                  ROUND(AVG(s.quantity),1) AS avg_qty, SUM(s.sale_price*s.quantity) AS revenue
           FROM sales_records s JOIN goods g ON s.goods_id = g.goods_id
           WHERE s.sale_date >= CURDATE() - INTERVAL %s DAY
           GROUP BY g.goods_id
           ORDER BY total_qty DESC LIMIT %s""",
        (days, limit),
    )
    return {"days": days, "rank": rows}


# ============================================================
# 工具5：近N天滞销榜 —— 供数据分析Agent
# ============================================================
@app.get("/api/sales/slow", summary="近N天滞销榜")
def sales_slow(days: int = Query(7, ge=1, le=90), limit: int = Query(10, ge=1, le=50)):
    rows = query(
        """SELECT g.goods_id, g.name, g.category, SUM(s.quantity) AS total_qty,
                  ROUND(AVG(s.quantity),1) AS avg_qty
           FROM sales_records s JOIN goods g ON s.goods_id = g.goods_id
           WHERE s.sale_date >= CURDATE() - INTERVAL %s DAY
           GROUP BY g.goods_id
           ORDER BY total_qty ASC LIMIT %s""",
        (days, limit),
    )
    return {"days": days, "rank": rows}


# ============================================================
# 工具6：补货建议（规则型预测：近7天均销 + 库存可售天数 + 前后7天趋势）
# —— 供预测决策Agent；每条建议附依据和置信度，供验证Agent核对
# ============================================================
@app.get("/api/restock/suggest", summary="补货进货建议")
def restock_suggest(days: int = Query(7, ge=3, le=30)):
    # 近 days 天日均销量
    cur = query(
        """SELECT g.goods_id, g.name, g.stock,
                  ROUND(SUM(s.quantity)/%s,1) AS avg_qty,
                  SUM(s.quantity) AS total_qty
           FROM goods g LEFT JOIN sales_records s
                  ON s.goods_id=g.goods_id AND s.sale_date >= CURDATE()-INTERVAL %s DAY
           GROUP BY g.goods_id""",
        (days, days),
    )
    # 前一个周期（第 days+1 ~ 2*days 天）日均销量，算趋势
    prev = {
        r["goods_id"]: r["avg_qty"]
        for r in query(
            """SELECT goods_id, ROUND(SUM(quantity)/%s,1) AS avg_qty
               FROM sales_records
               WHERE sale_date BETWEEN CURDATE()-INTERVAL %s DAY AND CURDATE()-INTERVAL %s DAY
               GROUP BY goods_id""",
            (days, 2 * days, days),
        )
    }

    result = []
    for r in cur:
        gid = r["goods_id"]
        avg_qty = r["avg_qty"] or 0
        stock = r["stock"]
        prev_avg = prev.get(gid, 0) or 0
        trend = round(avg_qty - prev_avg, 1)  # 正=上升，负=下滑
        # 库存可售天数：日均为0时给一个很大的数
        sellable_days = round(stock / avg_qty, 1) if avg_qty > 0 else 999

        if avg_qty >= 30 and sellable_days < 10:
            action, confidence = "建议多进", 0.88
        elif avg_qty <= 8 and stock >= 50:
            action, confidence = "建议少进/停进", 0.82
        else:
            action, confidence = "维持现有进货量", 0.7

        result.append({
            "goods_id": gid,
            "name": r["name"],
            "stock": stock,
            "avg_daily_qty": avg_qty,
            "prev_avg_qty": prev_avg,
            "trend": trend,
            "sellable_days": sellable_days,
            "suggestion": action,
            "confidence": confidence,
            "reason": f"近{days}天日均{avg_qty}，库存可售约{sellable_days}天，趋势{trend:+.1f}/天",
        })

    result.sort(key=lambda x: x["confidence"], reverse=True)

    # 中文汇总：一眼看出多进/少进名单
    multi = [s["name"] for s in result if s["suggestion"] == "建议多进"]
    reduce_ = [s["name"] for s in result if s["suggestion"] == "建议少进/停进"]
    keep = [s["name"] for s in result if s["suggestion"] == "维持现有进货量"]
    return {
        "days": days,
        "汇总": {
            "建议多进": multi,
            "建议少进或停进": reduce_,
            "维持现状": keep,
        },
        "suggestions": result,
    }


# ============================================================
# 工具7：一致性核验（验证Agent专用）
# 输入模型声称的价格/库存，与数据库真实值比对，返回是否一致与置信度
# ============================================================
class VerifyReq(BaseModel):
    goods_id: int
    claimed_price: float | None = None
    claimed_stock: int | None = None


@app.post("/api/verify/consistency", summary="核验Agent输出与数据库是否一致")
def verify_consistency(req: VerifyReq):
    row = query_one(
        "SELECT name, price, promo_price, is_promo, stock FROM goods WHERE goods_id=%s",
        (req.goods_id,),
    )
    if not row:
        raise HTTPException(status_code=404, detail="商品不存在")

    # 有效售价：当日特惠品用特惠价，否则用正常价（与消费者看到的展示价口径一致）
    on_promo = bool(row["is_promo"]) and row["promo_price"] is not None
    effective_price = float(row["promo_price"]) if on_promo else float(row["price"])

    checks = []
    passed_count = 0
    if req.claimed_price is not None:
        ok = abs(float(req.claimed_price) - effective_price) < 0.01
        price_label = "当日特惠价" if on_promo else "正常价"
        checks.append({"field": "price", "claimed": req.claimed_price,
                       "actual": effective_price, "matched": ok,
                       "note": f"库内为{price_label}"})
        passed_count += int(ok)
    if req.claimed_stock is not None:
        ok = int(req.claimed_stock) == int(row["stock"])
        checks.append({"field": "stock", "claimed": req.claimed_stock,
                       "actual": row["stock"], "matched": ok})
        passed_count += int(ok)

    total = len(checks)
    confidence = round(passed_count / total, 2) if total else 1.0
    return {
        "goods": row["name"],
        "checks": checks,
        "passed": passed_count == total,
        "confidence": confidence,
    }


# ============================================================
# 工具8：统一编排入口（调度引擎 + PDCA自循环）
# Dify 主Agent只挂这一个工具，由后端完成 意图识别→分派→执行→验证→自循环
# ============================================================
@app.post("/api/orchestrate", summary="统一编排入口（调度+验证+PDCA）")
def orchestrate(req: OrchReq):
    import traceback
    try:
        return orchestrator.run(req.query)
    except Exception as e:
        return {"error": repr(e), "trace": traceback.format_exc()}


# ============================================================
# 工具9：反馈记录（反馈记忆闭环）
# 用户/管理层对建议给出采纳或否决，写入 feedback 表供后续自优化
# ============================================================
class FeedbackReq(BaseModel):
    user_role: str            # consumer / manager
    goods_id: int | None = None
    content: str = ""
    adopted: int = 1          # 1采纳 0否决


@app.post("/api/feedback", summary="记录用户反馈（采纳/否决）")
def feedback(req: FeedbackReq):
    import traceback
    try:
        query(
            """INSERT INTO feedback (user_role, related_log_id, content, adopted)
               VALUES (%s,%s,%s,%s)""",
            (req.user_role, req.goods_id, req.content, req.adopted),
        )
        return {"status": "recorded", "adopted": req.adopted}
    except Exception as e:
        return {"error": repr(e), "trace": traceback.format_exc()}


# 静态门面页：访问 http://127.0.0.1:8000/ 直接打开统一前端
from fastapi.staticfiles import StaticFiles
app.mount("/", StaticFiles(directory=".", html=True), name="static")

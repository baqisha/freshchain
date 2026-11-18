# -*- coding: utf-8 -*-
"""
鲜智链 FreshChain 阶段1：模拟数据灌入脚本
功能：写入20种生鲜商品 + 生成最近45天销售流水（含热销/平稳/滞销趋势）
依赖：pymysql  ->  先执行: pip install pymysql
使用：连接参数优先读环境变量（MYSQL_HOST/PORT/USER/PASSWORD/DATABASE），
     未设置时回退下方默认值；本地手动跑改密码或设环境变量，Docker 由 compose 注入。
"""

import os
import random
from datetime import date, timedelta

import pymysql


def _env(name, default):
    v = os.environ.get(name)
    return default if v is None or v == "" else v


# ====================== 连接配置（环境变量优先，缺失回退默认） ======================
CONFIG = {
    "host": _env("MYSQL_HOST", "localhost"),
    "port": int(_env("MYSQL_PORT", 3306)),
    "user": _env("MYSQL_USER", "root"),
    "password": _env("MYSQL_PASSWORD", "在这里填你的MySQL密码"),  # 本地手动跑请改这里或设环境变量
    "database": _env("MYSQL_DATABASE", "freshchain"),
    "charset": "utf8mb4",
}
# ====================================================================

# 商品清单：(名称, 分类, 单位, 正常价, 保质期天数, 储存提示, 是否今日特惠, 特惠价, 销量档)
# 销量档位：hot=热销(高且缓升) / stable=平稳 / cold=滞销(低)
GOODS = [
    ("西红柿", "蔬菜", "斤", 4.99, 5, "阴凉处保存，勿冷藏，表皮红润有光泽为佳", 1, 3.99, "hot"),
    ("上海青", "蔬菜", "斤", 3.50, 3, "保鲜袋装好放冰箱冷藏，菜叶翠绿无黄叶为佳", 0, None, "stable"),
    ("土豆", "蔬菜", "斤", 2.99, 20, "避光存放防止发芽，表皮完整无芽眼为佳", 0, None, "stable"),
    ("胡萝卜", "蔬菜", "斤", 3.20, 10, "带泥新鲜，手感沉实，颜色橙红为佳", 0, None, "stable"),
    ("黄瓜", "蔬菜", "斤", 3.99, 5, "刺密、顶花带刺的更新鲜，常温可放2天", 0, None, "stable"),
    ("西兰花", "蔬菜", "斤", 6.80, 4, "花球紧实深绿，焯水后凉拌或清炒", 0, None, "cold"),
    ("菠菜", "蔬菜", "斤", 3.50, 3, "现买现吃最佳，根部带红更鲜嫩", 0, None, "cold"),
    ("洋葱", "蔬菜", "斤", 2.60, 25, "通风干燥处存放，表皮干燥有光泽", 0, None, "cold"),
    ("苹果", "水果", "斤", 6.99, 15, "脆甜多汁，均匀着色为佳，常温可放一周", 1, 5.49, "hot"),
    ("香蕉", "水果", "斤", 4.50, 5, "表皮微黄即可食用，勿冷藏", 1, 3.69, "hot"),
    ("西瓜", "水果", "个", 19.90, 7, "纹路清晰、拍声沉闷的更甜，现切现吃", 0, None, "stable"),
    ("草莓", "水果", "盒", 12.80, 2, "鲜红饱满、无软烂，冷藏并尽快食用", 0, None, "stable"),
    ("橙子", "水果", "斤", 5.80, 15, "手感沉重水分足，果皮细腻为佳", 0, None, "cold"),
    ("鸡蛋", "蛋奶", "个", 0.89, 30, "大头朝上冷藏，摇晃无声为新鲜", 1, 0.69, "hot"),
    ("牛奶", "蛋奶", "盒", 5.50, 7, "冷藏保存，看生产日期，乳白均匀为佳", 0, None, "stable"),
    ("鸡胸肉", "肉禽", "斤", 13.90, 2, "粉红色有弹性，冷藏1~2天内吃完", 0, None, "stable"),
    ("排骨", "肉禽", "斤", 28.80, 3, "新鲜红润带少许脂肪，炖汤红烧皆宜", 1, 23.90, "hot"),
    ("五花肉", "肉禽", "斤", 22.50, 3, "肥瘦层次分明，按紧实有弹性", 0, None, "stable"),
    ("鲫鱼", "水产", "斤", 15.60, 1, "现杀最佳，鳃红鳞亮，当日食用", 0, None, "cold"),
    ("豆腐", "豆制品", "盒", 3.20, 2, "当日购买当日食用，豆香清新不发酸", 0, None, "stable"),
]

# 销量档位每日随机区间：(下限, 上限)
TIRE_BASE = {
    "hot":    (35, 55),   # 热销：基数高，且随时间缓慢上升
    "stable": (15, 26),   # 平稳：中等
    "cold":   (2, 9),     # 滞销：低
}

DAYS = 45  # 生成最近45天的销售记录


def main():
    random.seed(42)  # 固定随机种子，保证每次运行数据一致（便于复现演示）
    conn = pymysql.connect(**CONFIG)
    try:
        with conn.cursor() as cur:
            # 1) 清空旧数据并写入商品
            cur.execute("DELETE FROM sales_records;")
            cur.execute("DELETE FROM goods;")
            sql_good = """INSERT INTO goods
                          (name, category, unit, price, shelf_life_days, storage_tip,
                           is_promo, promo_price, stock)
                          VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s)"""
            good_info = []  # (goods_id, 销量档, 正常价)
            for name, cat, unit, price, shelf, tip, promo, promo_price, tier in GOODS:
                stock = random.randint(80, 300)
                cur.execute(sql_good, (name, cat, unit, price, shelf, tip,
                                       promo, promo_price, stock))
                good_info.append((cur.lastrowid, tier, price))

            # 2) 生成最近45天销售流水
            today = date.today()
            start = today - timedelta(days=DAYS - 1)
            sql_sale = """INSERT INTO sales_records
                          (goods_id, sale_date, quantity, sale_price, channel)
                          VALUES (%s,%s,%s,%s,%s)"""
            sale_count = 0
            for i in range(DAYS):
                day = start + timedelta(days=i)
                trend = i / DAYS  # 0 -> 1，热销品随时间缓慢上升
                for gid, tier, price in good_info:
                    low, high = TIRE_BASE[tier]
                    qty = random.randint(low, high)
                    if tier == "hot":
                        qty = int(qty * (1 + 0.5 * trend))  # 越近卖得越好
                    channel = "线上" if random.random() < 0.35 else "到店"
                    cur.execute(sql_sale, (gid, day, qty, price, channel))
                    sale_count += 1
        conn.commit()
        print(f"✅ 商品写入完成：{len(GOODS)} 种")
        print(f"✅ 销售流水写入完成：{sale_count} 条（最近{DAYS}天）")
    finally:
        conn.close()


if __name__ == "__main__":
    main()

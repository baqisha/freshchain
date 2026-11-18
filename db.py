# -*- coding: utf-8 -*-
"""FreshChain 数据库连接模块：所有工具接口共用一个连接入口

连接参数优先读环境变量（MYSQL_HOST / MYSQL_PORT / MYSQL_USER /
MYSQL_PASSWORD / MYSQL_DATABASE），未设置时回退到下方默认值，
本地手动运行无需改代码；Docker 一键复现时由 compose 注入环境变量。
代码内不写任何真实密码。
"""

import os

import pymysql


def _env(name, default):
    v = os.environ.get(name)
    return default if v is None or v == "" else v


# ====================== 连接配置（环境变量优先，缺失回退默认） ======================
DB_CONFIG = {
    "host": _env("MYSQL_HOST", "localhost"),
    "port": int(_env("MYSQL_PORT", 3306)),
    "user": _env("MYSQL_USER", "root"),
    "password": _env("MYSQL_PASSWORD", "在这里填你的MySQL密码"),  # 本地手动跑请改这里或设环境变量
    "database": _env("MYSQL_DATABASE", "freshchain"),
    "charset": "utf8mb4",
    "cursorclass": pymysql.cursors.DictCursor,  # 结果返回成字典，方便转 JSON
}
# ======================================================================================


def get_conn():
    """获取一个新的数据库连接"""
    return pymysql.connect(**DB_CONFIG)


def query(sql: str, args: tuple = None):
    """查询多行，返回字典列表（写操作也在此提交）"""
    conn = get_conn()
    try:
        with conn.cursor(pymysql.cursors.DictCursor) as cur:
            cur.execute(sql, args or ())
            conn.commit()
            return list(cur.fetchall())
    finally:
        conn.close()


def query_one(sql: str, args: tuple = None):
    """查询单行，返回一个字典或 None"""
    conn = get_conn()
    try:
        with conn.cursor(pymysql.cursors.DictCursor) as cur:
            cur.execute(sql, args or ())
            return cur.fetchone()
    finally:
        conn.close()

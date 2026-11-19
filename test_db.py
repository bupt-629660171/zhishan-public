import sqlite3

conn = sqlite3.connect('food.db')
cursor = conn.cursor()

print("--- 正在扫描数据库所有数据 ---")

# 联表查询，把菜名、地点、窗口全查出来
cursor.execute('''
    SELECT Dish.name, Canteen.location, Canteen.window_name, Canteen.price
    FROM Dish
    JOIN Canteen ON Dish.id = Canteen.dish_id
''')

results = cursor.fetchall()

if not results:
    print("❌ 数据库里空空如也，没有任何数据！")
else:
    print(f"✅ 找到了 {len(results)} 条售卖记录：")
    for row in results:
        print(f"🍲 菜名: {row[0]} | 地点: {row[1]} | 窗口: {row[2]} | 价格: ￥{row[3]}")

conn.close()
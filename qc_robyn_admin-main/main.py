from robyn import Robyn, Response, jsonify
from qc_robyn_admin.core import AdminSite, MenuItem
import os
from testdemo.tables import Student, StudentID
from testdemo.initdata import init_data as app_init_data
from testdemo.admin import StudentAdmin
import orjson

if __name__ == "__main__":
    # 运行数据初始化 
    app = Robyn(__file__)
    # 服务目录
    app.serve_directory(
    route="/static",
        directory_path=os.path.join(os.getcwd(), "static"),
    )
    
    admin_site = AdminSite(
            app,
            title="QC Robyn Admin",
            prefix="admin",
            copyright="© 2024 Company Name. All rights reserved",
            db_url="sqlite://student.sqlite3",
            modules=None,
            # modules={"models": ["testdemo.tables"]},
            default_language="zh_CN",
            generate_schemas=True,
        )
    admin_site.register_menu(MenuItem(
        name="学生管理",
        icon="bi bi-gear",
        order=1
    ))

    admin_site.register_model(Student, StudentAdmin)
    # admin_site.register_model(StudentID, StudentIDAdmin)

    # 定义初始化数据路由
    @app.get("/api/init_data")
    async def init_data():
        # await app_init_data()
        return jsonify({"message": "数据初始化完成"})

    @app.get("/")
    async def index():
        # 返回json，中文正常显示
        output_binary = orjson.dumps({"messsage": "添加成功"})
        output_str = output_binary.decode("utf-8")
        return Response(
            status_code=200,
            description=output_str,
            headers={"Content-Type": "application/json;charset=utf-8"},
        )
    
    app.start(port=8180)


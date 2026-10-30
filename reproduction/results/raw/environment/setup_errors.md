# 环境配置时实际遇到的错误

1. 第一次安装日志重定向失败：日志父目录尚未创建。随后先建立 results/raw/environment，再成功安装。
2. 首次 check_environment.py 在独立 Windows venv 启动时失败：ZoneInfoNotFoundError: No time zone found with key Asia/Shanghai（tzdata 未安装）。诊断脚本改用显式 UTC+08:00 时区，不增加依赖，未修改作者源码。
3. 一次历史文件核查命令在 reproduction 根目录而非 upstream 下执行，报 not a git repository；已在 upstream 中读取正确历史文件。
4. 历史 cache_dataflow_function.py 在 150419a、e72115f 提交不存在；经 git log 确认从 29ca96e 提交读取成功。

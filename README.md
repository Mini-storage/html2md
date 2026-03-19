# html2md
一个简单的网页抓取并转换为md文档

### 安装依赖

```python
pip install requests beautifulsoup4 markdownify readability-lxml lxml
```

### 使用方式

交互式输入

```python
python web2md.py
# 然后粘贴网址回车即可
```

直接传入网址

```python
python web2md.py https://blog.csdn.net/xxx/article/xxx
```

指定输出文件名

```python
python web2md.py -o linux_commands.md https://blog.csdn.net/xxx
```

### 功能

| 功能              | 说明                                                         |
| ----------------- | ------------------------------------------------------------ |
| **智能正文提取**  | 使用 `readability-lxml` 自动识别主体内容，过滤广告/导航/评论区 |
| **广告过滤**      | 正则匹配清除常见广告 class/id（ad, banner, sidebar 等）      |
| **自动文件名**    | 根据文章标题生成合法的 `.md` 文件名                          |
| **自动补全链接**  | 修复文中相对路径链接                                         |
| **SSL 容错**      | SSL 验证失败时自动降级重试                                   |
| **编码自动检测**  | 防止中文乱码                                                 |
| **Markdown 格式** | 输出包含来源URL和抓取时间的标准 Markdown                     |

注：有些平台有登录墙保护，部分内容可能需要在浏览器登录后用 Cookie 才能完整抓取。

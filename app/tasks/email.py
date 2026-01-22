"""
提供邮件SMTP异步发送服务
"""

import email
import smtplib
from email.header import Header
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.utils import formataddr  # ✅ 新增：用于标准化发信地址格式

from flask import render_template

from app import celery


@celery.task(name="tasks.email_task", time_limit=35)
def email_task(
    to_address,
    subject,
    html_content=None,
    text_content=None,
    reply_address=None,
    from_address=None,
    from_username=None, # 注意：这里的语义被修正为“发件人昵称/别名”
):
    """发送邮件"""
    # 1. 检查配置开关
    if not celery.conf.app_config.get("ENABLE_USER_EMAIL"):
        return "未开启用户邮件配置"

    # 2. 读取配置
    conf = celery.conf.app_config
    email_smtp_host = conf.get("EMAIL_SMTP_HOST")
    email_smtp_port = int(conf.get("EMAIL_SMTP_PORT", 465))
    email_use_ssl = conf.get("EMAIL_USE_SSL")

    # 账号凭证 (用于登录 SMTP)
    email_account = conf.get("EMAIL_ADDRESS")
    email_password = conf.get("EMAIL_PASSWORD")

    # 默认值处理
    # 如果调用时没传 from_address，则使用配置中的发信邮箱
    current_from_email = from_address if from_address else email_account

    # 确定“发件人显示名称” (即 Alias，例如 "keli")
    # 优先级：函数参数 > 配置文件 > 默认邮箱前缀
    config_sender_name = conf.get("EMAIL_SENDER_NAME")

    if from_username:
        display_name = from_username
    elif config_sender_name:
        display_name = config_sender_name
    else:
        display_name = ""

    # 处理回复地址
    if reply_address is None:
        reply_address = conf.get("EMAIL_REPLY_ADDRESS")

    # 3. 构建邮件对象
    msg = MIMEMultipart("alternative")
    msg["Subject"] = Header(subject, 'utf-8').encode()

    # ✅ 核心修复：使用 formataddr 生成标准的 "Name <email@domain.com>" 格式
    # 这解决了腾讯云报错 "InvalidParameterValue"
    msg["From"] = formataddr((display_name, current_from_email))

    # 处理收件人 (支持列表或字符串)
    if isinstance(to_address, list):
        msg["To"] = ",".join(to_address)
    else:
        msg["To"] = to_address

    msg["Reply-to"] = reply_address
    msg["Message-id"] = email.utils.make_msgid()
    msg["Date"] = email.utils.formatdate()

    # 构建邮件正文
    if html_content:
        text_html = MIMEText(html_content, _subtype="html", _charset="UTF-8")
        msg.attach(text_html)

    if text_content:
        text_plain = MIMEText(text_content, _subtype="plain", _charset="UTF-8")
        msg.attach(text_plain)

    # 4. 发送邮件
    client = None
    try:
        # ✅ 修复超时：增加 timeout=10 防止 Worker 卡死
        if email_use_ssl:
            client = smtplib.SMTP_SSL(email_smtp_host, email_smtp_port, timeout=10)
        else:
            client = smtplib.SMTP(email_smtp_host, email_smtp_port, timeout=10)
            try:
                client.starttls()
            except smtplib.SMTPNotSupportedError:
                pass

        # client.set_debuglevel(1) # 调试时可开启

        # ✅ 核心修复：登录必须使用“配置的账号”，而不是“显示别名”
        # 原代码 client.login(from_username, ...) 是错误的，会导致认证失败
        client.login(email_account, email_password)

        # 发送
        # 注意：sendmail 的第一个参数 (Envelope From) 必须是经过验证的邮箱地址
        client.sendmail(current_from_email, to_address, msg.as_string())
        client.quit()
        return "发送成功"

    except smtplib.SMTPConnectError as e:
        return f"发送失败，连接失败: {e.smtp_code} {e.smtp_error}"
    except smtplib.SMTPAuthenticationError as e:
        return f"发送失败，认证错误: {e.smtp_code} {e.smtp_error}"
    except smtplib.SMTPSenderRefused as e:
        return f"发送失败，发件人被拒绝: {e.smtp_code} {e.smtp_error}"
    except smtplib.SMTPRecipientsRefused as e:
        return f"发送失败，收件人被拒绝: {e.smtp_code} {e.smtp_error}"
    except smtplib.SMTPDataError as e:
        return f"发送失败，数据接收拒绝: {e.smtp_code} {e.smtp_error}"
    except smtplib.SMTPException as e:
        # ✅ 修复 AttributeError: Python3 异常没有 .message 属性
        return f"发送失败, SMTP异常: {str(e)}"
    except Exception as e:
        return f"发送异常, 未知错误: {str(e)}"


def send_email(
    to_address,
    subject,
    html_content=None,
    text_content=None,
    reply_address=None,
    from_address=None,
    from_username=None,
    template=None,
    template_data=None,
):
    """
    对外调用的发送接口
    """
    # 如果提供了模板，则使用模板创建内容
    if template:
        # 确保 template_data 不是 None
        data = template_data if template_data else {}
        html_content = render_template(template + ".html", **data)
        # 尝试渲染 txt 模板，如果不存在可能会报错，建议加个 try-except 或者确保文件存在
        try:
            text_content = render_template(template + ".txt", **data)
        except Exception:
            pass # 忽略 txt 模板缺失

    email_task.delay(
        to_address,
        subject,
        html_content,
        text_content,
        reply_address,
        from_address,
        from_username,
    )

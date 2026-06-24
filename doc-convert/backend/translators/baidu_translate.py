# -*- coding: utf-8 -*-
"""
百度翻译 API 集成
文档：https://fanyi-api.baidu.com/product/13
"""
import os
import random
import time
from hashlib import md5
from typing import List, Optional

import requests


class TranslationQuotaExceeded(Exception):
    """翻译配额已用完"""
    pass


class BaiduTranslator:
    """百度翻译API客户端（支持主备账号自动切换）"""

    ENDPOINT = 'http://api.fanyi.baidu.com'
    PATH = '/api/trans/vip/translate'
    IMAGE_PATH = '/api/trans/sdk/picture'  # 图片识别API

    # 语言代码映射
    LANG_MAP = {
        'zh': 'zh',      # 中文
        'en': 'en',      # 英文
        'auto': 'auto',  # 自动检测
    }

    def __init__(self, appid: Optional[str] = None, appkey: Optional[str] = None):
        """
        初始化翻译客户端（支持主备账号）

        Args:
            appid: 主账号 APP ID（环境变量 BAIDU_TRANSLATE_APPID）
            appkey: 主账号 APP KEY（环境变量 BAIDU_TRANSLATE_APPKEY）

        备用账号从环境变量自动加载：
            BAIDU_TRANSLATE_backup_APPID
            BAIDU_TRANSLATE_backup_APPKEY
        """
        # 主账号
        self.primary_appid = appid or os.getenv('BAIDU_TRANSLATE_APPID')
        self.primary_appkey = appkey or os.getenv('BAIDU_TRANSLATE_APPKEY')

        # 备用账号
        self.backup_appid = os.getenv('BAIDU_TRANSLATE_backup_APPID')
        self.backup_appkey = os.getenv('BAIDU_TRANSLATE_backup_APPKEY')

        # 当前使用的账号（默认主账号）
        self.current_appid = self.primary_appid
        self.current_appkey = self.primary_appkey
        self.using_backup = False

        if not self.primary_appid or not self.primary_appkey:
            raise ValueError(
                "百度翻译 API 配置缺失。请设置环境变量：\n"
                "BAIDU_TRANSLATE_APPID=your_appid\n"
                "BAIDU_TRANSLATE_APPKEY=your_appkey"
            )

        # 检查备用账号
        self.has_backup = bool(self.backup_appid and self.backup_appkey)
        if self.has_backup:
            print(f"[百度翻译] 已配置备用账号，主账号限额后将自动切换")

    def _switch_to_backup(self):
        """切换到备用账号"""
        if not self.has_backup:
            return False

        if self.using_backup:
            # 已经在用备用账号了
            return False

        print(f"[百度翻译] 主账号限额用完，切换到备用账号")
        self.current_appid = self.backup_appid
        self.current_appkey = self.backup_appkey
        self.using_backup = True
        return True

    @staticmethod
    def _make_md5(s: str, encoding='utf-8') -> str:
        """生成 MD5 签名"""
        return md5(s.encode(encoding)).hexdigest()

    def recognize_image(
        self,
        image_bytes: bytes,
        from_lang: str = 'auto',
        to_lang: str = 'zh',
        retry: int = 3
    ) -> Optional[dict]:
        """
        图片识别 + 翻译（百度通用图片OCR API）
        文档：https://fanyi-api.baidu.com/doc/26

        Args:
            image_bytes: 图片二进制数据（PNG/JPG/BMP，最大 4MB）
            from_lang: 源语言（auto/zh/en）
            to_lang: 目标语言（zh/en）
            retry: 失败重试次数

        Returns:
            dict: {
                'original_text': str,     # 识别的原文（拼接所有行）
                'translated_text': str,   # 翻译结果（拼接所有行）
                'blocks': List[dict]      # 文本块列表（含位置信息）
            }
            失败返回 None
        """
        if not image_bytes:
            return None

        # 检查大小（百度限制 4MB）
        if len(image_bytes) > 4 * 1024 * 1024:
            raise ValueError(f"图片过大（{len(image_bytes) / 1024 / 1024:.1f}MB > 4MB）")

        salt = str(random.randint(32768, 65536))
        # 签名：appid + md5(image) + salt + cuid + mac + 密钥
        cuid = 'APICUID'  # 固定值
        mac = 'mac'  # 固定值
        sign_str = self.current_appid + md5(image_bytes).hexdigest() + salt + cuid + mac + self.current_appkey
        sign = self._make_md5(sign_str)

        # 构建 multipart/form-data
        files = {
            'image': ('image.png', image_bytes, 'image/png')
        }

        data = {
            'from': from_lang,
            'to': to_lang,
            'cuid': cuid,
            'mac': mac,
            'version': '3',
            'salt': salt,
            'sign': sign,
            'appid': self.current_appid,
            'paste': '0'  # 不需要图片贴合
        }

        url = self.ENDPOINT + self.IMAGE_PATH

        for attempt in range(retry):
            try:
                response = requests.post(url, data=data, files=files, timeout=30)
                result = response.json()

                # 检查错误
                if 'error_code' in result:
                    error_code = str(result['error_code'])
                    error_msg = result.get('error_msg', 'Unknown error')

                    # 错误码 '0' 表示成功，继续处理
                    if error_code == '0':
                        pass  # 成功，继续下面的提取结果
                    # 54003: QPS 超限
                    elif error_code == '54003' and attempt < retry - 1:
                        time.sleep(1)
                        continue
                    # 54004/54001: 限额用完
                    elif error_code in ['54004', '54001']:
                        account_type = "备用账号" if self.using_backup else "主账号"
                        raise TranslationQuotaExceeded(f"{account_type}图片识别限额已用完")
                    else:
                        raise Exception(f"百度图片识别 API 错误 {error_code}: {error_msg}")

                # 提取结果
                if 'data' in result and 'content' in result['data']:
                    blocks = result['data']['content']

                    # 提取原文和译文（每个 block 就是一个文本块，src 和 dst 已配对）
                    original_lines = []
                    translated_lines = []

                    for block in blocks:
                        src = block.get('src', '').strip()
                        dst = block.get('dst', '').strip()

                        # 跳过空块
                        if src and dst:
                            original_lines.append(src)
                            translated_lines.append(dst)

                    return {
                        'original_text': '\n'.join(original_lines),
                        'translated_text': '\n'.join(translated_lines),
                        'blocks': blocks
                    }

                return None

            except requests.RequestException as e:
                if attempt == retry - 1:
                    raise Exception(f"百度图片识别 API 请求失败: {str(e)}")
                time.sleep(0.5)

        return None

    def translate(
        self,
        text: str,
        from_lang: str = 'auto',
        to_lang: str = 'zh',
        retry: int = 3
    ) -> Optional[str]:
        """
        翻译文本

        Args:
            text: 待翻译文本（最大 6000 字符）
            from_lang: 源语言代码（auto/zh/en）
            to_lang: 目标语言代码（zh/en）
            retry: 失败重试次数

        Returns:
            翻译后的文本，失败返回 None
        """
        if not text or not text.strip():
            return text

        # 限制长度（百度API单次最大6000字符）
        if len(text) > 6000:
            raise ValueError(f"单次翻译文本过长（{len(text)} > 6000字符）")

        salt = str(random.randint(32768, 65536))
        sign = self._make_md5(self.current_appid + text + salt + self.current_appkey)

        params = {
            'appid': self.current_appid,
            'q': text,
            'from': from_lang,
            'to': to_lang,
            'salt': salt,
            'sign': sign
        }

        headers = {'Content-Type': 'application/x-www-form-urlencoded'}
        url = self.ENDPOINT + self.PATH

        for attempt in range(retry):
            try:
                response = requests.post(url, params=params, headers=headers, timeout=10)
                result = response.json()

                # 检查错误
                if 'error_code' in result:
                    error_code = result['error_code']
                    error_msg = result.get('error_msg', 'Unknown error')

                    # 54003: QPS 超限，等待后重试
                    if error_code == '54003' and attempt < retry - 1:
                        time.sleep(1)
                        continue

                    # 54004/54001: 限额用完（月度/账户余额不足）
                    if error_code in ['54004', '54001']:
                        account_type = "备用账号" if self.using_backup else "主账号"
                        raise TranslationQuotaExceeded(f"{account_type}限额已用完")

                    raise Exception(f"百度翻译 API 错误 {error_code}: {error_msg}")

                # 提取翻译结果
                if 'trans_result' in result and result['trans_result']:
                    translations = [item['dst'] for item in result['trans_result']]
                    return '\n'.join(translations)

                return None

            except requests.RequestException as e:
                if attempt == retry - 1:
                    raise Exception(f"百度翻译 API 请求失败: {str(e)}")
                time.sleep(0.5)

        return None

    def translate_batch(
        self,
        texts: List[str],
        from_lang: str = 'auto',
        to_lang: str = 'zh',
        progress_callback=None
    ) -> dict:
        """
        批量翻译文本（并行 + 智能限速 + 容错）

        Args:
            texts: 待翻译文本列表
            from_lang: 源语言
            to_lang: 目标语言
            progress_callback: 进度回调 callback(current, total)

        Returns:
            dict: {
                'results': List[str],  # 翻译结果（失败的保留原文）
                'success_count': int,   # 成功翻译数量
                'total': int,           # 总数
                'quota_exceeded': bool, # 是否限额
                'error': Optional[str]  # 错误信息
            }
        """
        from concurrent.futures import ThreadPoolExecutor, as_completed
        import threading

        results = [None] * len(texts)
        total = len(texts)
        completed = 0
        success_count = 0
        quota_exceeded = False
        error_message = None
        lock = threading.Lock()

        # QPS 限速器（8 QPS = 每秒最多 8 个请求）
        last_request_times = []
        qps_limit = 8
        qps_lock = threading.Lock()

        def rate_limited_translate(index: int, text: str):
            """限速翻译单个文本"""
            nonlocal completed, success_count, quota_exceeded, error_message

            # QPS 限速：检查最近 1 秒内的请求数
            with qps_lock:
                now = time.time()
                # 清理 1 秒前的记录
                last_request_times[:] = [t for t in last_request_times if now - t < 1.0]

                # 如果超过限制，等待
                if len(last_request_times) >= qps_limit:
                    sleep_time = 1.0 - (now - last_request_times[0])
                    if sleep_time > 0:
                        time.sleep(sleep_time)
                    # 重新清理
                    now = time.time()
                    last_request_times[:] = [t for t in last_request_times if now - t < 1.0]

                # 记录本次请求时间
                last_request_times.append(now)

            # 执行翻译（捕获限额异常）
            try:
                translated = self.translate(text, from_lang, to_lang)
                results[index] = translated or text

                with lock:
                    success_count += 1
            except TranslationQuotaExceeded as e:
                # 限额用完，尝试切换到备用账号
                with lock:
                    if not self.using_backup and self._switch_to_backup():
                        # 成功切换到备用账号，重试当前翻译
                        try:
                            translated = self.translate(text, from_lang, to_lang)
                            results[index] = translated or text
                            success_count += 1
                        except Exception:
                            # 备用账号也失败，保留原文
                            results[index] = text
                            quota_exceeded = True
                            if not error_message:
                                error_message = "主账号和备用账号限额均已用完"
                    else:
                        # 无备用账号或备用账号也限额了
                        results[index] = text
                        quota_exceeded = True
                        if not error_message:
                            if self.using_backup:
                                error_message = "主账号和备用账号限额均已用完"
                            else:
                                error_message = "翻译 API 限额已用完（无备用账号）"
            except Exception as e:
                # 其他错误，保留原文
                results[index] = text
                with lock:
                    if not error_message:
                        error_message = f"翻译失败: {str(e)}"

            # 更新进度
            with lock:
                completed += 1
                if progress_callback:
                    progress_callback(completed, total)

        # 并行翻译（8 个线程，匹配 QPS 限制）
        max_workers = min(8, len(texts))
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            futures = {executor.submit(rate_limited_translate, i, text): i
                      for i, text in enumerate(texts)}

            # 等待所有完成
            for future in as_completed(futures):
                try:
                    future.result()
                except Exception:
                    pass  # 已在内部处理

        return {
            'results': results,
            'success_count': success_count,
            'total': total,
            'quota_exceeded': quota_exceeded,
            'error': error_message
        }


# 全局单例
_translator_instance: Optional[BaiduTranslator] = None


def get_translator() -> BaiduTranslator:
    """获取全局翻译器实例（单例模式）"""
    global _translator_instance
    if _translator_instance is None:
        _translator_instance = BaiduTranslator()
    return _translator_instance

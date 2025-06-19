import re
from typing import Any, List, Dict, Tuple, Optional
from urllib.parse import urljoin
import json

from cachetools import cached, TTLCache

from app import schemas
from app.core.config import settings
from app.core.event import eventmanager, Event
from app.log import logger
from app.plugins import _PluginBase
from app.schemas import DiscoverSourceEventData
from app.schemas.types import ChainEventType
from app.utils.http import RequestUtils


class JavdbDiscover(_PluginBase):
    # 插件名称
    plugin_name = "JavDB探索"
    # 插件描述
    plugin_desc = "让探索支持JavDB的数据浏览，并提供JAV影片识别增强功能。"
    # 插件图标
    plugin_icon = "Bilibili_E.png"
    # 插件版本
    plugin_version = "1.2.2"
    # 插件作者
    plugin_author = "KINAXNG"
    # 作者主页
    author_url = "https://github.com/KINAXNG"
    # 插件配置项ID前缀
    plugin_config_prefix = "javdbdiscover_"
    # 加载顺序
    plugin_order = 99
    # 可使用的用户级别
    auth_level = 1

    # 私有属性
    _base_api = "https://javdb.com"
    _enabled = False
    _proxy = False
    _api_key = None
    _recognize = False

    def init_plugin(self, config: dict = None):
        if config:
            self._enabled = config.get("enabled")
            self._proxy = config.get("proxy")
            self._api_key = config.get("api_key")
            self._recognize = config.get("recognize")

    def get_state(self) -> bool:
        return self._enabled

    @staticmethod
    def get_command() -> List[Dict[str, Any]]:
        pass

    def get_api(self) -> List[Dict[str, Any]]:
        """
        获取插件API
        """
        return [{
            "path": "/javdb_discover",
            "endpoint": self.javdb_discover,
            "methods": ["GET"],
            "summary": "JavDB探索数据源",
            "description": "获取JavDB探索数据",
        }]

    def get_form(self) -> Tuple[List[dict], Dict[str, Any]]:
        """
        拼装插件配置页面，需要返回两块数据：1、页面配置；2、数据结构
        """
        return [
            {
                'component': 'VForm',
                'content': [
                    {
                        'component': 'VRow',
                        'content': [
                            {
                                'component': 'VCol',
                                'props': {
                                    'cols': 12,
                                    'md': 4
                                },
                                'content': [
                                    {
                                        'component': 'VSwitch',
                                        'props': {
                                            'model': 'enabled',
                                            'label': '启用插件',
                                        }
                                    }
                                ]
                            },
                            {
                                'component': 'VCol',
                                'props': {
                                    'cols': 12,
                                    'md': 4
                                },
                                'content': [
                                    {
                                        'component': 'VSwitch',
                                        'props': {
                                            'model': 'proxy',
                                            'label': '使用代理服务器',
                                        }
                                    }
                                ]
                            },
                            {
                                'component': 'VCol',
                                'props': {
                                    'cols': 12,
                                    'md': 4
                                },
                                'content': [
                                    {
                                        'component': 'VSwitch',
                                        'props': {
                                            'model': 'recognize',
                                            'label': '辅助识别',
                                        }
                                    }
                                ]
                            }
                        ]
                    },
                    {
                        'component': 'VRow',
                        'content': [
                            {
                                'component': 'VCol',
                                'props': {
                                    'cols': 12
                                },
                                'content': [
                                    {
                                        'component': 'VTextField',
                                        'props': {
                                            'model': 'api_key',
                                            'label': 'Cookie',
                                            'placeholder': '请输入JavDB的Cookie'
                                        }
                                    }
                                ]
                            }
                        ]
                    },
                    {
                        'component': 'VRow',
                        'content': [
                            {
                                'component': 'VCol',
                                'props': {
                                    'cols': 12,
                                },
                                'content': [
                                    {
                                        'component': 'VAlert',
                                        'props': {
                                            'type': 'info',
                                            'variant': 'tonal',
                                            'text': '开启插件后，可以在探索页面浏览JavDB内容。开启辅助识别后，当文件名包含JAV番号时，将自动从JavDB获取影片信息并生成兼容IMDB的数据结构，提升JAV影片的识别成功率。配置Cookie可以获取更完整的内容数据。'
                                        }
                                    }
                                ]
                            }
                        ]
                    }
                ]
            }
        ], {
            "enabled": False,
            "proxy": False,
            "api_key": "",
            "recognize": False
        }

    def get_page(self) -> List[dict]:
        pass

    def get_service(self) -> List[Dict[str, Any]]:
        """
        注册插件公共服务
        """
        return []

    def get_module(self) -> Dict[str, Any]:
        """
        获取插件模块声明，用于胁持系统模块实现（方法名：方法实现）
        """
        pass

    @cached(cache=TTLCache(maxsize=32, ttl=1800))
    def __request(self, path: str, **kwargs) -> str:
        """
        请求JavDB API
        """
        api_url = f"{self._base_api}/{path}"
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
            "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
            "Accept-Encoding": "gzip, deflate, br",
            "Connection": "keep-alive",
            "Upgrade-Insecure-Requests": "1",
            "Referer": "https://javdb.com/"
        }
        if self._api_key:
            headers["Cookie"] = self._api_key
            
        res = RequestUtils(headers=headers).get_res(
            api_url,
            params=kwargs,
            proxies=settings.PROXY if self._proxy else None
        )
        if res is None:
            raise Exception("无法连接JavDB，请检查网络连接！")
        if not res.ok:
            raise Exception(f"请求JavDB失败：{res.text}")
        return res.text

    def javdb_discover(self, apikey: str, keyword: str = "", mtype: str = "all",
                       page: int = 1, count: int = 30) -> List[schemas.MediaInfo]:
        """
        获取JavDB探索数据
        """
        if apikey != settings.API_TOKEN:
            return []
        
        if not self._enabled:
            logger.warning("JavDB探索插件未启用")
            return []
        
        if not self._api_key:
            logger.warning("JavDB Cookie未配置，可能无法获取完整数据")

        try:
            # 构建搜索路径，参考tissue项目的实现
            if keyword:
                # 搜索模式
                path = f"search?q={keyword}&f=all"
                if page > 1:
                    path += f"&page={page}"
            else:
                # 浏览模式 - 获取热门内容
                if mtype == "censored":
                    path = f"?c=1&page={page}"
                elif mtype == "uncensored":
                    path = f"?c=2&page={page}"
                elif mtype == "western":
                    path = f"?c=3&page={page}"
                else:
                    # 默认显示最新内容
                    path = f"?page={page}"
            
            # 获取HTML内容
            html_content = self.__request(path)
            
            # 解析HTML并提取影片信息
            medias = self.__parse_html(html_content, count)
            
            return medias[:count]
            
        except Exception as e:
            logger.error(f"获取JavDB数据失败: {str(e)}")
            return []

    def __parse_html(self, html_content: str, count: int) -> List[schemas.MediaInfo]:
        """
        解析HTML内容并提取影片信息，参考tissue项目的解析方式
        """
        medias = []
        
        try:
            # 更精确的正则表达式，参考tissue项目的实现
            # 匹配影片卡片
            pattern = r'<div class="item".*?>\s*<a href="([^"]+)".*?>\s*<div class="cover".*?>\s*<img[^>]+src="([^"]+)"[^>]*>.*?</div>\s*</a>\s*<div class="meta">\s*<a href="[^"]*".*?>\s*<strong>([^<]+)</strong>'
            matches = re.findall(pattern, html_content, re.DOTALL)
            
            if not matches:
                # 尝试更宽松的匹配
                pattern = r'<div class="item">.*?<a href="([^"]+)".*?<img[^>]+src="([^"]+)"[^>]*>.*?<strong>([^<]+)</strong>'
                matches = re.findall(pattern, html_content, re.DOTALL)
            
            for i, (url, image, title) in enumerate(matches):
                if i >= count:
                    break
                    
                # 构建完整URL
                detail_url = urljoin(self._base_api, url) if not url.startswith('http') else url
                image_url = urljoin(self._base_api, image) if not image.startswith('http') else image
                
                # 提取影片ID
                video_id = url.split('/')[-1] if '/' in url else title.strip()
                
                # 清理标题
                clean_title = title.strip()
                
                media = schemas.MediaInfo(
                    type="电影",
                    title=clean_title,
                    year="",
                    title_year=clean_title,
                    mediaid_prefix="javdb",
                    media_id=video_id,
                    poster_path=image_url,
                    overview="",
                    vote_average=0,
                    release_date="",
                    detail_link=detail_url
                )
                medias.append(media)
                
        except Exception as e:
            logger.error(f"解析JavDB HTML失败: {str(e)}")
            
        return medias

    @staticmethod
    def javdb_filter_ui() -> List[dict]:
        """
        JavDB过滤UI，参考tissue项目的分类
        """
        return [
            {
                "component": "div",
                "props": {
                    "class": "flex justify-start items-center mb-3"
                },
                "content": [
                    {
                        "component": "div",
                        "props": {
                            "class": "mr-5"
                        },
                        "content": [
                            {
                                "component": "VLabel",
                                "text": "类型"
                            }
                        ]
                    },
                    {
                        "component": "VChipGroup",
                        "props": {
                            "model": "mtype"
                        },
                        "content": [
                            {
                                "component": "VChip",
                                "props": {
                                    "filter": True,
                                    "tile": True,
                                    "value": "all"
                                },
                                "text": "全部"
                            },
                            {
                                "component": "VChip",
                                "props": {
                                    "filter": True,
                                    "tile": True,
                                    "value": "censored"
                                },
                                "text": "有码"
                            },
                            {
                                "component": "VChip",
                                "props": {
                                    "filter": True,
                                    "tile": True,
                                    "value": "uncensored"
                                },
                                "text": "无码"
                            },
                            {
                                "component": "VChip",
                                "props": {
                                    "filter": True,
                                    "tile": True,
                                    "value": "western"
                                },
                                "text": "欧美"
                            }
                        ]
                    }
                ]
            },
            {
                "component": "div",
                "props": {
                    "class": "flex justify-start items-center"
                },
                "content": [
                    {
                        "component": "div",
                        "props": {
                            "class": "mr-5"
                        },
                        "content": [
                            {
                                "component": "VLabel",
                                "text": "搜索"
                            }
                        ]
                    },
                    {
                        "component": "VTextField",
                        "props": {
                            "model": "keyword",
                            "label": "关键词",
                            "placeholder": "输入搜索关键词"
                        }
                    }
                ]
            }
        ]

    def __is_jav_code(self, filename: str) -> Optional[str]:
        """
        检查文件名是否包含JAV番号
        """
        # 常见的JAV番号格式
        jav_patterns = [
            r'\b([A-Z]{2,6}-?\d{3,4})\b',  # ABC-123, ABCD-1234
            r'\b(\d{6}[-_]\d{3})\b',       # 123456-123, 123456_123
            r'\b([A-Z]{1,2}\d{3,4})\b',    # A123, AB1234
            r'\b(T28-\d{3})\b',            # T28-123
            r'\b(FC2-PPV-\d+)\b',          # FC2-PPV-123456
            r'\b(HEYZO-\d{4})\b',          # HEYZO-1234
            r'\b(1PON-\d{6}_\d{3})\b',     # 1PON-123456_123
            r'\b(CARIB-\d{6}-\d{3})\b',    # CARIB-123456-123
        ]
        
        for pattern in jav_patterns:
            match = re.search(pattern, filename, re.IGNORECASE)
            if match:
                return match.group(1).upper()
        return None

    def __generate_fake_imdb_id(self, jav_code: str) -> str:
        """
        为JAV番号生成一个伪IMDB ID，确保系统兼容性
        """
        # 使用一个固定的前缀和JAV番号的哈希来生成伪IMDB ID
        import hashlib
        hash_obj = hashlib.md5(jav_code.encode())
        # 取前7位数字，确保是7位数的IMDB ID格式
        hash_num = str(int(hash_obj.hexdigest()[:8], 16))[:7].zfill(7)
        return f"tt9{hash_num}"  # tt9前缀表示这是伪造的IMDB ID

    def __get_javdb_media_info(self, jav_code: str) -> Optional[schemas.MediaInfo]:
        """
        从JavDB获取影片详细信息
        """
        try:
            # 搜索影片
            search_path = f"search?q={jav_code}&f=all"
            html_content = self.__request(search_path)
            
            # 解析搜索结果，找到第一个匹配的影片
            pattern = r'<div class="item".*?>\s*<a href="([^"]+)".*?>\s*<div class="cover".*?>\s*<img[^>]+src="([^"]+)"[^>]*>.*?</div>\s*</a>\s*<div class="meta">\s*<a href="[^"]*".*?>\s*<strong>([^<]+)</strong>'
            matches = re.findall(pattern, html_content, re.DOTALL)
            
            if not matches:
                logger.debug(f"未在JavDB中找到番号: {jav_code}")
                return None
            
            # 获取第一个结果的详细信息
            url, image, title = matches[0]
            detail_url = urljoin(self._base_api, url) if not url.startswith('http') else url
            image_url = urljoin(self._base_api, image) if not image.startswith('http') else image
            
            # 获取详情页面以获取更多信息
            detail_path = url.lstrip('/')
            detail_html = self.__request(detail_path)
            
            # 解析详情页面获取更多信息
            overview = self.__extract_overview(detail_html)
            year = self.__extract_year(detail_html)
            performers = self.__extract_performers(detail_html)
            
            # 生成伪IMDB ID以确保系统兼容性
            fake_imdb_id = self.__generate_fake_imdb_id(jav_code)
            
            # 构建MediaInfo
            media_info = schemas.MediaInfo(
                type="电影",
                title=title.strip(),
                year=year,
                title_year=f"{title.strip()} ({year})" if year else title.strip(),
                mediaid_prefix="javdb",
                media_id=jav_code,
                poster_path=image_url,
                overview=overview,
                vote_average=0,
                release_date="",
                detail_link=detail_url,
                cast=performers,
                imdb_id=fake_imdb_id  # 添加伪IMDB ID
            )
            
            logger.info(f"成功从JavDB获取到影片信息: {title} ({jav_code}) [伪IMDB: {fake_imdb_id}]")
            return media_info
            
        except Exception as e:
            logger.error(f"从JavDB获取影片信息失败 {jav_code}: {str(e)}")
            return None

    def __extract_overview(self, html: str) -> str:
        """从详情页面提取简介"""
        try:
            # 尝试提取简介信息
            overview_pattern = r'<div class="panel-block"[^>]*>\s*<p[^>]*>([^<]+)</p>'
            match = re.search(overview_pattern, html, re.DOTALL)
            if match:
                return match.group(1).strip()
        except:
            pass
        return ""

    def __extract_year(self, html: str) -> str:
        """从详情页面提取年份"""
        try:
            # 尝试提取发行日期中的年份
            year_pattern = r'<span class="value">(\d{4})-\d{2}-\d{2}</span>'
            match = re.search(year_pattern, html)
            if match:
                return match.group(1)
        except:
            pass
        return ""

    def __extract_performers(self, html: str) -> List[str]:
        """从详情页面提取演员信息"""
        try:
            # 尝试提取演员信息
            performers = []
            performer_pattern = r'<a href="/actors/[^"]*"[^>]*>([^<]+)</a>'
            matches = re.findall(performer_pattern, html)
            for match in matches:
                performers.append(match.strip())
            return performers[:5]  # 最多返回5个演员
        except:
            pass
        return []

    @eventmanager.register(ChainEventType.NameRecognize)
    def name_recognize_enhance(self, event: Event):
        """
        名称识别增强事件监听 - 提升JAV影片识别
        """
        if not self._enabled or not self._recognize:
            return
            
        # 获取事件数据
        event_data = event.event_data
        if not event_data:
            return
            
        # 检查文件路径或名称
        file_path = event_data.get("file_path", "")
        file_name = event_data.get("file_name", "")
        
        # 检查文件名是否包含JAV番号
        jav_code = self.__is_jav_code(file_name or file_path)
        if not jav_code:
            return
            
        logger.info(f"检测到JAV番号: {jav_code} in {file_name or file_path}")
        
        # 从JavDB获取影片信息
        media_info = self.__get_javdb_media_info(jav_code)
        if media_info:
            # 添加到识别结果中
            if "media_info" not in event_data:
                event_data["media_info"] = []
            event_data["media_info"].append(media_info.__dict__)
            logger.info(f"成功识别JAV影片: {media_info.title}")



    @eventmanager.register(ChainEventType.DiscoverSource)
    def discover_source(self, event: Event):
        """
        监听识别事件，注册探索数据源
        """
        if not self._enabled:
            return
            
        event_data: DiscoverSourceEventData = event.event_data
        
        # 注册JavDB数据源
        javdb_source = schemas.DiscoverMediaSource(
            name="JavDB",
            mediaid_prefix="javdb",
            api_path=f"plugin/JavdbDiscover/javdb_discover?apikey={settings.API_TOKEN}",
            filter_params={
                "keyword": "",
                "mtype": "all",
            },
            filter_ui=self.javdb_filter_ui()
        )
        if not event_data.extra_sources:
            event_data.extra_sources = [javdb_source]
        else:
            event_data.extra_sources.append(javdb_source)

    def stop_service(self):
        """
        退出插件
        """
        pass

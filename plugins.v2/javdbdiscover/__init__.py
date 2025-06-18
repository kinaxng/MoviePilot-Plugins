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
    plugin_desc = "让探索支持JavDB的数据浏览。"
    # 插件图标
    plugin_icon = "Bilibili_E.png"
    # 插件版本
    plugin_version = "1.0"
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

    def init_plugin(self, config: dict = None):
        if config:
            self._enabled = config.get("enabled")
            self._proxy = config.get("proxy")
            self._api_key = config.get("api_key")

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
                    }
                ]
            }
        ], {
            "enabled": False,
            "proxy": False,
            "api_key": ""
        }

    def get_page(self) -> List[dict]:
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
            logger.warning("JavDB Cookie未配置，无法获取数据")
            return []

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

    @eventmanager.register(ChainEventType.DiscoverSource)
    def discover_source(self, event: Event):
        """
        监听识别事件，注册探索数据源
        """
        if not self._enabled or not self._api_key:
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

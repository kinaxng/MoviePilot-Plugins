import re
from typing import Any, List, Dict, Tuple, Optional
from urllib.parse import urljoin

from cachetools import cached, TTLCache

from app import schemas
from app.core.config import settings
from app.core.event import eventmanager, Event
from app.log import logger
from app.plugins import _PluginBase
from app.schemas import DiscoverSourceEventData
from app.schemas.types import ChainEventType
from app.utils.http import RequestUtils


class TvdbDiscover(_PluginBase):
    # 插件名称
    plugin_name = "TheTVDB探索"
    # 插件描述
    plugin_desc = "让探索支持TheTVDB的数据浏览。"
    # 插件图标
    plugin_icon = "TheTVDB_A.png"
    # 插件版本
    plugin_version = "1.1"
    # 插件作者
    plugin_author = "jxxghp"
    # 作者主页
    author_url = "https://github.com/jxxghp"
    # 插件配置项ID前缀
    plugin_config_prefix = "tvdbdiscover_"
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
        [{
            "path": "/xx",
            "endpoint": self.xxx,
            "methods": ["GET", "POST"],
            "summary": "API说明"
        }]
        """
        return [{
            "path": "/tvdb_discover",
            "endpoint": self.tvdb_discover,
            "methods": ["GET"],
            "summary": "TheTVDB探索数据源",
            "description": "获取TheTVDB探索数据",
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
                                            'label': 'API Key',
                                            'placeholder': '请输入TheTVDB的Cookie'
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
        请求TheTVDB API
        """
        api_url = f"{self._base_api}/{path}"
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
            "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
            "Accept-Encoding": "gzip, deflate, br",
            "Connection": "keep-alive",
            "Upgrade-Insecure-Requests": "1"
        }
        if self._api_key:
            headers["Cookie"] = self._api_key
            
        res = RequestUtils(headers=headers).get_res(
            api_url,
            params=kwargs,
            proxies=settings.PROXY if self._proxy else None
        )
        if res is None:
            raise Exception("无法连接TheTVDB，请检查网络连接！")
        if not res.ok:
            raise Exception(f"请求TheTVDB API失败：{res.text}")
        return res.text

    def tvdb_discover(self, apikey: str, mtype: str = "series",
                      company: int = None, contentRating: int = None, country: str = "usa",
                      genre: int = None, lang: str = "eng", sort: str = "score", sortType: str = "desc",
                      status: int = None, year: int = None,
                      page: int = 1, count: int = 30) -> List[schemas.MediaInfo]:
        """
        获取TheTVDB探索数据
        """
        if apikey != settings.API_TOKEN:
            return []
        
        if not self._enabled:
            logger.warning("TheTVDB探索插件未启用")
            return []
        
        if not self._api_key:
            logger.warning("TheTVDB API Key未配置，无法获取数据")
            return []

        try:
            # 构建搜索路径 - 实际使用JavDB的路径
            if mtype == "movies":
                path = "rankings/video_views"
            else:
                path = "rankings/video_views"
            
            # 添加分页参数
            if page > 1:
                path += f"?page={page}"
            
            # 获取HTML内容
            html_content = self.__request(path)
            
            # 解析HTML并提取影片信息
            medias = self.__parse_html(html_content, count)
            
            return medias[:count]
            
        except Exception as e:
            logger.error(f"获取TheTVDB数据失败: {str(e)}")
            return []

    def __parse_html(self, html_content: str, count: int) -> List[schemas.MediaInfo]:
        """
        解析HTML内容并提取影片信息
        """
        medias = []
        
        try:
            # 使用正则表达式提取影片信息
            # 根据JavDB的实际HTML结构调整
            pattern = r'<div class="item">.*?<a href="([^"]+)".*?<img[^>]+src="([^"]+)"[^>]*>.*?<div class="uid">([^<]+)</div>.*?</div>'
            matches = re.findall(pattern, html_content, re.DOTALL)
            
            for i, (url, image, title) in enumerate(matches):
                if i >= count:
                    break
                    
                # 构建完整URL
                detail_url = urljoin(self._base_api, url)
                image_url = urljoin(self._base_api, image) if not image.startswith('http') else image
                
                # 提取影片ID
                video_id = url.split('/')[-1] if '/' in url else title
                
                # 伪装成TheTVDB的数据格式
                media = schemas.MediaInfo(
                    type="电影" if "movies" in url else "电视剧",
                    title=title.strip(),
                    year="",
                    title_year=title.strip(),
                    mediaid_prefix="tvdb",  # 伪装成tvdb
                    media_id=video_id,
                    poster_path=image_url,
                    overview="",
                    vote_average=0,
                    release_date=""
                )
                medias.append(media)
                
        except Exception as e:
            logger.error(f"解析TheTVDB HTML失败: {str(e)}")
            
        return medias

    @staticmethod
    def tvdb_filter_ui() -> List[dict]:
        """
        TheTVDB过滤UI - 简化版
        """
        return [
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
                                    "value": "movies"
                                },
                                "text": "电影"
                            },
                            {
                                "component": "VChip",
                                "props": {
                                    "filter": True,
                                    "tile": True,
                                    "value": "series"
                                },
                                "text": "电视剧"
                            }
                        ]
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
        
        # 注册TheTVDB数据源（实际是JavDB）
        tvdb_source = schemas.DiscoverMediaSource(
            name="TheTVDB",  # 显示名称保持TheTVDB
            mediaid_prefix="tvdb",  # 保持tvdb前缀
            api_path=f"plugin/TvdbDiscover/tvdb_discover?apikey={settings.API_TOKEN}",
            filter_params={
                "mtype": "series",
                "company": None,
                "contentRating": None,
                "country": "usa",
                "genre": None,
                "lang": "eng",
                "sort": "score",
                "sortType": "desc",
                "status": None,
                "year": None,
            },
            filter_ui=self.tvdb_filter_ui()
        )
        if not event_data.extra_sources:
            event_data.extra_sources = [tvdb_source]
        else:
            event_data.extra_sources.append(tvdb_source)

    def stop_service(self):
        """
        退出插件
        """
        pass

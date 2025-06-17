from typing import Any, List, Dict, Tuple, Optional

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
    plugin_version = "0.1"
    # 插件作者
    plugin_author = "copilot"
    # 作者主页
    author_url = "https://github.com/chris-2s/tissue"
    # 插件配置项ID前缀
    plugin_config_prefix = "javdbdiscover_"
    # 加载顺序
    plugin_order = 1
    # 可使用的用户级别
    auth_level = 1

    # 私有属性
    _base_api = "https://javdb.com"
    _enabled = False
    _proxy = False
    _cookie = None

    def init_plugin(self, config: dict = None):
        if config:
            self._enabled = config.get("enabled")
            self._proxy = config.get("proxy")
            self._cookie = config.get("cookie")

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
                                            'model': 'cookie',
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
            "cookie": ""
        }

    def get_page(self) -> List[dict]:
        pass

    def __request(self, path: str, **kwargs):
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
            "Upgrade-Insecure-Requests": "1"
        }
        if self._cookie:
            headers["Cookie"] = self._cookie
            
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

    def javdb_discover(self, apikey: str, keyword: str = "",
                       page: int = 1, count: int = 30) -> List[schemas.MediaInfo]:
        """
        获取JavDB探索数据
        """
        if not self._enabled:
            return []
        
        if not self._cookie:
            logger.warning("JavDB Cookie未配置，无法获取数据")
            return []

        try:
            # 构建搜索路径
            if keyword:
                path = f"search?q={keyword}&f=all"
            else:
                path = "rankings/video_views"
            
            # 添加分页参数
            if page > 1:
                path += f"&page={page}"
            
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
        解析HTML内容并提取影片信息
        """
        import re
        from urllib.parse import urljoin
        
        medias = []
        
        try:
            # 使用正则表达式提取影片信息
            # 这里需要根据实际的JavDB HTML结构调整
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
                
                media = schemas.MediaInfo(
                    mediaid=f"javdb:{video_id}",
                    title=title.strip(),
                    overview="",
                    poster_path=image_url,
                    backdrop_path=image_url,
                    vote_average=0,
                    release_date="",
                    year="",
                    type_name="电影",
                    detail_link=detail_url
                )
                medias.append(media)
                
        except Exception as e:
            logger.error(f"解析JavDB HTML失败: {str(e)}")
            
        return medias

    @staticmethod
    def javdb_filter_ui() -> List[dict]:
        """
        JavDB过滤UI
        """
        return [
            {
                'component': 'VRow',
                'content': [
                    {
                        'component': 'VCol',
                        'props': {
                            'cols': 12,
                            'md': 6
                        },
                        'content': [
                            {
                                'component': 'VTextField',
                                'props': {
                                    'model': 'keyword',
                                    'label': '搜索关键词',
                                    'placeholder': '输入搜索关键词'
                                }
                            }
                        ]
                    }
                ]
            }
        ]

    @eventmanager.register(ChainEventType.DiscoverSource)
    def discover_source(self, event: Event):
        """
        注册探索数据源
        """
        if not self._enabled:
            return
        
        if not self._cookie:
            logger.warning("JavDB Cookie未配置，跳过注册探索数据源")
            return

        event_data: DiscoverSourceEventData = event.event_data
        
        # 添加JavDB数据源
        extra_source = schemas.DiscoverMediaSource(
            name="JavDB",
            mediaid_prefix="javdb",
            api_path="/javdb_discover",
            filter_params={
                "keyword": "搜索关键词"
            },
            filter_ui=self.javdb_filter_ui()
        )
        
        event_data.extra_sources.append(extra_source)

    def stop_service(self):
        """
        退出插件
        """
        pass

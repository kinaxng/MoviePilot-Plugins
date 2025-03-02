from typing import Any, List, Dict, Tuple, Optional
import re
from datetime import datetime

from cachetools import cached, TTLCache

from app import schemas
from app.core.config import settings
from app.core.event import eventmanager, Event
from app.log import logger
from app.plugins import _PluginBase
from app.schemas import DiscoverSourceEventData
from app.schemas.types import ChainEventType
from app.utils.http import RequestUtils


class MTeamDiscover(_PluginBase):
    # 插件名称
    plugin_name = "馒头探索"
    # 插件描述
    plugin_desc = "让探索支持馒头的数据浏览。"
    # 插件图标
    plugin_icon = "MTeam.png"
    # 插件版本
    plugin_version = "1.0"
    # 插件作者
    plugin_author = "kinaxng"
    # 作者主页
    author_url = "https://github.com/kinaxng"
    # 插件配置项ID前缀
    plugin_config_prefix = "mteamdiscover_"
    # 加载顺序
    plugin_order = 99
    # 可使用的用户级别
    auth_level = 1

    # 私有属性
    _base_api = "https://kp.m-team.cc"
    _enabled = False
    _proxy = False
    _username = None
    _password = None
    _cookie = None

    def init_plugin(self, config: dict = None):
        if config:
            self._enabled = config.get("enabled")
            self._proxy = config.get("proxy")
            self._username = config.get("username")
            self._password = config.get("password")
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
            "path": "/mteam_discover",
            "endpoint": self.mteam_discover,
            "methods": ["GET"],
            "summary": "M-Team探索数据源",
            "description": "获取M-Team探索数据",
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
                                    'cols': 12,
                                    'md': 6
                                },
                                'content': [
                                    {
                                        'component': 'VTextField',
                                        'props': {
                                            'model': 'username',
                                            'label': '用户名',
                                            'placeholder': '请输入M-Team用户名'
                                        }
                                    }
                                ]
                            },
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
                                            'model': 'password',
                                            'label': '密码',
                                            'type': 'password',
                                            'placeholder': '请输入M-Team密码'
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
                                            'label': 'Cookie (可选)',
                                            'placeholder': '如已有Cookie可直接填入，格式如：uid=xxx; pass=xxx'
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
            "username": "",
            "password": "",
            "cookie": ""
        }

    def get_page(self) -> List[dict]:
        pass

    @cached(cache=TTLCache(maxsize=1, ttl=24 * 3600))
    def __get_cookie(self) -> Optional[str]:
        """
        获取Cookie
        """
        if self._cookie:
            return self._cookie
        
        if not self._username or not self._password:
            return None
            
        login_url = f"{self._base_api}/takelogin.php"
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
            "Referer": f"{self._base_api}/login.php"
        }
        data = {
            "username": self._username,
            "password": self._password
        }
        
        res = RequestUtils(headers=headers).post_res(
            login_url,
            data=data,
            proxies=settings.PROXY if self._proxy else None,
            allow_redirects=False
        )
        
        if not res or not res.cookies:
            logger.error("登录M-Team失败")
            return None
            
        cookies = '; '.join([f"{k}={v}" for k, v in res.cookies.items()])
        return cookies

    @cached(cache=TTLCache(maxsize=32, ttl=1800))
    def __request(self, category: int = 0, search: str = "", **kwargs):
        """
        请求M-Team API
        """
        api_url = f"{self._base_api}/torrents.php"
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
            "Cookie": self.__get_cookie()
        }
        
        params = {
            "cat": category
        }
        
        if search:
            params["search"] = search
            
        # 添加其他参数
        params.update(kwargs)
        
        res = RequestUtils(headers=headers).get_res(
            api_url,
            params=params,
            proxies=settings.PROXY if self._proxy else None
        )
        
        if res is None:
            raise Exception("无法连接M-Team，请检查网络连接！")
        if not res.ok:
            raise Exception(f"请求M-Team失败：{res.status_code}")
            
        return res.text

    def __parse_torrents(self, html_content: str) -> List[dict]:
        """
        解析种子列表
        """
        torrents = []
        
        # 使用正则表达式提取种子信息
        pattern = r'<tr class="(.*?)".*?id="(.*?)".*?<a href="details\.php\?id=(\d+)&amp;hit=1">(.*?)</a>.*?<a href="download\.php\?id=(\d+)".*?<td class="rowfollow nowrap"><span class="(.*?)">(.*?)</span>.*?<td class="rowfollow">(.*?)</td>.*?<td class="rowfollow">(.*?)</td>.*?<img class="(.*?)" src="(.*?)"'
        
        matches = re.finditer(pattern, html_content, re.DOTALL)
        
        for match in matches:
            try:
                torrent_id = match.group(3)
                title = match.group(4).strip()
                size = match.group(7).strip()
                upload_time = match.group(8).strip()
                seeder_count = match.group(9).strip()
                
                # 提取图片URL
                img_url = match.group(11)
                if not img_url.startswith("http"):
                    img_url = f"{self._base_api}/{img_url}"
                
                # 尝试从标题中提取年份
                year_match = re.search(r'\b(19\d{2}|20\d{2})\b', title)
                year = year_match.group(1) if year_match else None
                
                torrents.append({
                    "id": torrent_id,
                    "title": title,
                    "size": size,
                    "upload_time": upload_time,
                    "seeder_count": seeder_count,
                    "image": img_url,
                    "year": year
                })
            except Exception as e:
                logger.error(f"解析种子信息失败: {str(e)}")
                continue
                
        return torrents

    def mteam_discover(self, apikey: str, category: int = 0, search: str = "",
                      sort: str = "id", sortType: str = "desc",
                      page: int = 1, count: int = 30) -> List[schemas.MediaInfo]:
        """
        获取M-Team探索数据
        """
        def __torrent_to_media(torrent_info: dict) -> schemas.MediaInfo:
            """
            种子数据转换为MediaInfo
            """
            return schemas.MediaInfo(
                type="种子",
                title=torrent_info.get("title"),
                year=torrent_info.get("year"),
                title_year=f"{torrent_info.get('title')} ({torrent_info.get('year') or '未知'})",
                mediaid_prefix="mteam",
                media_id=str(torrent_info.get("id")),
                poster_path=torrent_info.get("image"),
                vote_average=float(torrent_info.get("seeder_count") or 0),
                overview=f"大小: {torrent_info.get('size')}\n上传时间: {torrent_info.get('upload_time')}\n做种数: {torrent_info.get('seeder_count')}"
            )

        if apikey != settings.API_TOKEN:
            return []
            
        try:
            html_content = self.__request(
                category=category,
                search=search,
                sort=sort,
                type=sortType,
                page=page
            )
            
            torrents = self.__parse_torrents(html_content)
            
            # 转换为MediaInfo格式
            results = [__torrent_to_media(torrent) for torrent in torrents]
            
            # 分页处理
            start_idx = (page - 1) * count
            end_idx = start_idx + count
            
            return results[start_idx:end_idx]
            
        except Exception as err:
            logger.error(str(err))
            return []

    @staticmethod
    def mteam_filter_ui() -> List[dict]:
        """
        M-Team过滤参数UI配置
        """
        # 分类字典
        category_dict = {
            "0": "全部",
            "401": "电影",
            "404": "电视剧",
            "405": "动漫",
            "402": "纪录片",
            "403": "综艺",
            "406": "音乐",
            "407": "体育",
            "408": "软件",
            "409": "游戏",
            "410": "其他"
        }

        category_ui = [
            {
                "component": "VChip",
                "props": {
                    "filter": True,
                    "tile": True,
                    "value": key
                },
                "text": value
            } for key, value in category_dict.items()
        ]

        # 排序字典
        sort_dict = {
            "id": "发布时间",
            "size": "文件大小",
            "seeders": "做种数",
            "leechers": "下载数",
            "completes": "完成数"
        }

        sort_ui = [
            {
                "component": "VChip",
                "props": {
                    "filter": True,
                    "tile": True,
                    "value": key
                },
                "text": value
            } for key, value in sort_dict.items()
        ]

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
                                "text": "分类"
                            }
                        ]
                    },
                    {
                        "component": "VChipGroup",
                        "props": {
                            "model": "category"
                        },
                        "content": category_ui
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
                                "text": "排序"
                            }
                        ]
                    },
                    {
                        "component": "VChipGroup",
                        "props": {
                            "model": "sort"
                        },
                        "content": sort_ui
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
                                "text": "排序方式"
                            }
                        ]
                    },
                    {
                        "component": "VChipGroup",
                        "props": {
                            "model": "sortType"
                        },
                        "content": [
                            {
                                "component": "VChip",
                                "props": {
                                    "filter": True,
                                    "tile": True,
                                    "value": "desc"
                                },
                                "text": "降序"
                            },
                            {
                                "component": "VChip",
                                "props": {
                                    "filter": True,
                                    "tile": True,
                                    "value": "asc"
                                },
                                "text": "升序"
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
                            "model": "search",
                            "placeholder": "输入关键词搜索",
                            "dense": True,
                            "hide-details": True
                        }
                    }
                ]
            }
        ]

    @eventmanager.register(ChainEventType.DiscoverSource)
    def discover_source(self, event: Event):
        """
        监听识别事件，添加M-Team数据源
        """
        if not self._enabled or not self._cookie and not (self._username and self._password):
            return
        event_data: DiscoverSourceEventData = event.event_data
        mteam_source = schemas.DiscoverMediaSource(
            name="M-Team",
            mediaid_prefix="mteam",
            api_path=f"plugin/MTeamDiscover/mteam_discover?apikey={settings.API_TOKEN}",
            filter_params={
                "category": 0,
                "search": "",
                "sort": "id",
                "sortType": "desc",
            },
            filter_ui=self.mteam_filter_ui()
        )
        if not event_data.extra_sources:
            event_data.extra_sources = [mteam_source]
        else:
            event_data.extra_sources.append(mteam_source)

    def stop_service(self):
        """
        退出插件
        """
        pass
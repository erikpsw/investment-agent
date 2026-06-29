"""Unified stock picking service.

The first pass is deliberately conservative: use price/sector-theme heuristics
to build a small candidate set, then let the LLM summarize only those candidates.
"""
from __future__ import annotations

import json
import math
import os
import re
import time
from concurrent.futures import ThreadPoolExecutor, TimeoutError, as_completed
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

import pandas as pd
import requests


PROJECT_ROOT = Path(__file__).resolve().parent.parent
STORAGE_DIR = PROJECT_ROOT / "storage" / "stock_picker"
REALTIME_DIR = PROJECT_ROOT / "storage" / "realtime_monitor"
SCORE_TIMEOUT_SECONDS = 55
SCORE_WORKERS = 12
LLM_TIMEOUT_SECONDS = 35
ENRICH_TIMEOUT_SECONDS = 8
ENRICH_WORKERS = 8


CANDIDATE_POOL: List[Dict[str, str]] = [
    {"ticker": "sz002156", "name": "通富微电", "market": "CN", "theme": "半导体封测", "profile": "core", "description": "国内先进封测龙头之一，覆盖集成电路封装测试、存储/计算芯片封测和车规/工业电子封测。"},
    {"ticker": "sh600584", "name": "长电科技", "market": "CN", "theme": "半导体封测", "profile": "core", "description": "全球封测头部企业，业务包括先进封装、系统级封装和晶圆级封装，受益AI芯片和国产半导体周期。"},
    {"ticker": "sh688187", "name": "时代电气", "market": "CN", "theme": "高端制造/功率半导体", "profile": "core"},
    {"ticker": "sz301666", "name": "江顺科技", "market": "CN", "theme": "创业板成长", "profile": "emerging"},
    {"ticker": "sh603115", "name": "海星股份", "market": "CN", "theme": "电子材料", "profile": "emerging", "description": "铝电解电容器用电极箔供应商，下游覆盖新能源、AI服务器、汽车电子和工业控制。"},
    {"ticker": "sz002738", "name": "中矿资源", "market": "CN", "theme": "锂资源", "profile": "core", "description": "锂盐、铯铷盐和矿权资源公司，受锂价周期、资源扩张和新能源需求影响较大。"},
    {"ticker": "sz002518", "name": "科士达", "market": "CN", "theme": "储能/电源", "profile": "core", "description": "UPS、数据中心电源和储能逆变器厂商，受益AI数据中心供电和工商业储能需求。"},
    {"ticker": "sh600703", "name": "三安光电", "market": "CN", "theme": "化合物半导体", "profile": "core", "description": "LED和化合物半导体平台型公司，布局SiC、GaN、射频和光电器件。"},
    {"ticker": "sh603986", "name": "兆易创新", "market": "CN", "theme": "存储/MCU", "profile": "core", "description": "国产NOR Flash、NAND和MCU龙头，跟随存储周期、端侧AI和消费电子复苏。"},
    {"ticker": "sz002371", "name": "北方华创", "market": "CN", "theme": "半导体设备", "profile": "mega", "description": "国产半导体设备龙头，覆盖刻蚀、薄膜、清洗等关键设备。"},
    {"ticker": "sz300474", "name": "景嘉微", "market": "CN", "theme": "国产GPU/军工芯片", "profile": "emerging"},
    {"ticker": "sz300308", "name": "中际旭创", "market": "CN", "theme": "AI光模块", "profile": "core"},
    {"ticker": "sz300502", "name": "新易盛", "market": "CN", "theme": "AI光模块", "profile": "core"},
    {"ticker": "sh688498", "name": "源杰科技", "market": "CN", "theme": "高速光芯片", "profile": "emerging"},
    {"ticker": "sh688205", "name": "德科立", "market": "CN", "theme": "光通信器件", "profile": "emerging"},
    {"ticker": "sh688332", "name": "中科蓝讯", "market": "CN", "theme": "端侧AI芯片", "profile": "emerging"},
    {"ticker": "sh688515", "name": "裕太微", "market": "CN", "theme": "车载以太网芯片", "profile": "emerging"},
    {"ticker": "sh688182", "name": "灿勤科技", "market": "CN", "theme": "卫星/通信陶瓷元件", "profile": "emerging"},
    {"ticker": "sh688375", "name": "国博电子", "market": "CN", "theme": "相控阵/军工电子", "profile": "emerging"},
    {"ticker": "sh688522", "name": "纳睿雷达", "market": "CN", "theme": "相控阵雷达", "profile": "emerging"},
    {"ticker": "sz300114", "name": "中航电测", "market": "CN", "theme": "军工/航空电子", "profile": "emerging"},
    {"ticker": "sz300101", "name": "振芯科技", "market": "CN", "theme": "北斗/卫星导航", "profile": "emerging"},
    {"ticker": "sz300045", "name": "华力创通", "market": "CN", "theme": "卫星通信/北斗", "profile": "emerging"},
    {"ticker": "sh688066", "name": "航天宏图", "market": "CN", "theme": "卫星遥感/数据", "profile": "emerging"},
    {"ticker": "sz002446", "name": "盛路通信", "market": "CN", "theme": "卫星通信/军工通信", "profile": "emerging", "description": "军工电子和通信天线厂商，覆盖微波组件、毫米波通信、卫星通信和车联网天线。"},
    {"ticker": "sz300394", "name": "天孚通信", "market": "CN", "theme": "AI光器件", "profile": "core"},
    {"ticker": "sz002463", "name": "沪电股份", "market": "CN", "theme": "AI服务器PCB", "profile": "core", "description": "高端PCB龙头，重点覆盖AI服务器、交换机、汽车电子和通信设备。"},
    {"ticker": "sh603228", "name": "景旺电子", "market": "CN", "theme": "PCB/汽车电子", "profile": "core", "description": "PCB和FPC厂商，服务汽车电子、服务器、通信和消费电子客户。"},
    {"ticker": "sz002916", "name": "深南电路", "market": "CN", "theme": "AI服务器PCB/封装基板", "profile": "core", "description": "高端PCB和封装基板平台，覆盖通信、数据中心、汽车电子和半导体封装。"},
    {"ticker": "sz002938", "name": "鹏鼎控股", "market": "CN", "theme": "消费电子/AI终端PCB", "profile": "core", "description": "全球PCB大厂，主要覆盖消费电子、服务器、汽车电子和AI终端电路板。"},
    {"ticker": "sh603920", "name": "世运电路", "market": "CN", "theme": "汽车电子/PCB", "profile": "emerging", "description": "PCB供应商，汽车电子、工业控制和新能源方向占比较高。"},
    {"ticker": "sh603712", "name": "七一二", "market": "CN", "theme": "军工通信/专网", "profile": "emerging", "description": "军用无线通信和专网通信设备厂商，受益国防信息化和低空/应急通信需求。"},
    {"ticker": "sh600562", "name": "国睿科技", "market": "CN", "theme": "雷达/军工电子", "profile": "emerging", "description": "雷达、轨交信号和工业软件相关业务，军工电子属性较强。"},
    {"ticker": "sh600118", "name": "中国卫星", "market": "CN", "theme": "卫星制造/航天", "profile": "core", "description": "小卫星制造和航天应用平台，受益商业航天、卫星互联网和遥感应用。"},
    {"ticker": "sh600879", "name": "航天电子", "market": "CN", "theme": "航天电子/军工", "profile": "core", "description": "航天电子设备、惯导、测控和电连接产品供应商。"},
    {"ticker": "sz002151", "name": "北斗星通", "market": "CN", "theme": "北斗导航/芯片", "profile": "emerging", "description": "北斗导航芯片、板卡和位置服务厂商，关联车载、无人机和低空经济。"},
    {"ticker": "sz002465", "name": "海格通信", "market": "CN", "theme": "军工通信/北斗", "profile": "core", "description": "军工通信、北斗导航和无线通信装备供应商。"},
    {"ticker": "sh603501", "name": "韦尔股份", "market": "CN", "theme": "图像传感器/汽车芯片", "profile": "core", "description": "CMOS图像传感器和模拟芯片龙头，关联手机、汽车电子和安防视觉。"},
    {"ticker": "sh603290", "name": "斯达半导", "market": "CN", "theme": "功率半导体/IGBT", "profile": "core", "description": "IGBT和功率模块厂商，服务新能源车、光伏、储能和工业控制。"},
    {"ticker": "sz002409", "name": "雅克科技", "market": "CN", "theme": "半导体材料", "profile": "core", "description": "半导体材料、电子特气和前驱体平台，受益国产材料替代。"},
    {"ticker": "sz002436", "name": "兴森科技", "market": "CN", "theme": "封装基板/PCB", "profile": "emerging", "description": "PCB样板和IC封装基板厂商，关注高端封装基板扩产兑现。"},
    {"ticker": "sz002049", "name": "紫光国微", "market": "CN", "theme": "安全芯片/特种IC", "profile": "core", "description": "特种集成电路和安全芯片厂商，军工电子和可信计算属性较强。"},
    {"ticker": "sh600206", "name": "有研新材", "market": "CN", "theme": "半导体材料/稀土", "profile": "emerging", "description": "电子材料、稀土材料和靶材相关公司，关联半导体材料国产化。"},
    {"ticker": "sz002185", "name": "华天科技", "market": "CN", "theme": "半导体封测", "profile": "emerging", "description": "国内封测公司，覆盖集成电路封装测试和先进封装升级。"},
    {"ticker": "sz002079", "name": "苏州固锝", "market": "CN", "theme": "分立器件/传感器", "profile": "emerging", "description": "半导体分立器件、传感器和封装业务，受益汽车电子和工业应用。"},
    {"ticker": "sh603728", "name": "鸣志电器", "market": "CN", "theme": "机器人/控制电机", "profile": "emerging", "description": "步进电机、控制电机和运动控制产品供应商，关联机器人和自动化。"},
    {"ticker": "sz002979", "name": "雷赛智能", "market": "CN", "theme": "运动控制/机器人", "profile": "emerging", "description": "运动控制产品供应商，覆盖伺服、步进和控制系统，下游包括机器人和自动化设备。"},
    {"ticker": "sz002896", "name": "中大力德", "market": "CN", "theme": "机器人减速器", "profile": "emerging", "description": "减速器、电机和驱动器厂商，具备机器人关节部件弹性。"},
    {"ticker": "sh603662", "name": "柯力传感", "market": "CN", "theme": "传感器/机器人", "profile": "emerging", "description": "力学传感器和称重物联网厂商，关联机器人力控和工业传感。"},
    {"ticker": "sz002335", "name": "科华数据", "market": "CN", "theme": "数据中心电源/储能", "profile": "core", "description": "数据中心电源、UPS、储能和新能源电力电子公司。"},
    {"ticker": "sh603063", "name": "禾望电气", "market": "CN", "theme": "风光储电力电子", "profile": "emerging", "description": "新能源电控、电力电子和储能变流器厂商。"},
    {"ticker": "sz002074", "name": "国轩高科", "market": "CN", "theme": "动力电池/储能", "profile": "core", "description": "动力电池和储能电池厂商，关注海外订单和储能需求。"},
    {"ticker": "sz002850", "name": "科达利", "market": "CN", "theme": "电池结构件", "profile": "core", "description": "锂电池精密结构件龙头，服务动力电池和储能电池客户。"},
    {"ticker": "sh603019", "name": "中科曙光", "market": "CN", "theme": "AI服务器/算力", "profile": "core", "description": "高性能计算、服务器和数据中心基础设施公司，国产算力主线核心标的。"},
    {"ticker": "sh600570", "name": "恒生电子", "market": "CN", "theme": "金融IT/AI应用", "profile": "core", "description": "金融IT软件龙头，服务券商、基金、银行和资管机构。"},
    {"ticker": "sz002230", "name": "科大讯飞", "market": "CN", "theme": "AI应用/大模型", "profile": "core", "description": "语音识别、教育AI和大模型应用公司，关注AI应用商业化兑现。"},
    {"ticker": "sz002402", "name": "和而泰", "market": "CN", "theme": "智能控制器/机器人", "profile": "emerging", "description": "智能控制器和家电/汽车电子控制板供应商，关联机器人、储能和智能家居控制。"},
    {"ticker": "sz002139", "name": "拓邦股份", "market": "CN", "theme": "智能控制器/储能", "profile": "emerging", "description": "智能控制器、电池和电机控制公司，下游覆盖工具、家电、新能源和机器人。"},
    {"ticker": "sz002444", "name": "巨星科技", "market": "CN", "theme": "机器人/工具出海", "profile": "core", "description": "手工具、智能工具和机器人相关设备出口公司，受益制造业出海和自动化工具需求。"},
    {"ticker": "sh603583", "name": "捷昌驱动", "market": "CN", "theme": "线性驱动/机器人", "profile": "emerging", "description": "线性驱动系统供应商，覆盖办公升降、医疗康护、工业自动化和机器人部件。"},
    {"ticker": "sh603308", "name": "应流股份", "market": "CN", "theme": "航空航天/高端铸件", "profile": "emerging", "description": "高端装备铸件和航空航天零部件公司，关联燃机、核电、航空发动机和工业母机。"},
    {"ticker": "sh600765", "name": "中航重机", "market": "CN", "theme": "航空锻造/军工", "profile": "core", "description": "航空锻铸件和液压环控业务平台，服务航空发动机、飞机结构件和军工装备。"},
    {"ticker": "sh600391", "name": "航发科技", "market": "CN", "theme": "航空发动机", "profile": "emerging", "description": "航空发动机和燃气轮机零部件供应商，受益航空发动机产业链景气。"},
    {"ticker": "sh600038", "name": "中直股份", "market": "CN", "theme": "直升机/低空经济", "profile": "core", "description": "直升机和航空装备平台，关联军用直升机、通航和低空经济装备。"},
    {"ticker": "sh600760", "name": "中航沈飞", "market": "CN", "theme": "航空主机/军工", "profile": "core", "description": "航空防务主机厂，军机产业链核心标的。"},
    {"ticker": "sh600316", "name": "洪都航空", "market": "CN", "theme": "航空装备/教练机", "profile": "emerging", "description": "航空装备和教练机平台，具备军工航空弹性。"},
    {"ticker": "sz002025", "name": "航天电器", "market": "CN", "theme": "军工连接器", "profile": "core", "description": "军用连接器、继电器和微特电机供应商，服务航天、航空、电子和通信装备。"},
    {"ticker": "sz002179", "name": "中航光电", "market": "CN", "theme": "军工连接器/新能源汽车", "profile": "core", "description": "高端连接器龙头，覆盖军工、通信、新能源汽车和工业装备。"},
    {"ticker": "sz002214", "name": "大立科技", "market": "CN", "theme": "红外热成像/军工", "profile": "emerging", "description": "红外热像仪和光电装备厂商，关联军工夜视、安防和工业检测。"},
    {"ticker": "sh600893", "name": "航发动力", "market": "CN", "theme": "航空发动机", "profile": "core", "description": "航空发动机整机和维修平台，是航空发动机主线核心标的。"},
    {"ticker": "sz002414", "name": "高德红外", "market": "CN", "theme": "红外探测/军工", "profile": "core", "description": "红外探测器、热像仪和光电系统厂商，覆盖军工、安防和民用红外。"},
    {"ticker": "sz002268", "name": "电科网安", "market": "CN", "theme": "网络安全/信创", "profile": "emerging", "description": "网络安全和密码安全产品公司，关联数据安全、信创和关键信息基础设施。"},
    {"ticker": "sz002212", "name": "天融信", "market": "CN", "theme": "网络安全/信创", "profile": "emerging", "description": "网络安全产品和安全服务厂商，覆盖防火墙、数据安全和云安全。"},
    {"ticker": "sh600845", "name": "宝信软件", "market": "CN", "theme": "工业软件/数据中心", "profile": "core", "description": "工业软件、IDC和企业信息化平台，服务钢铁制造、云计算和数据中心。"},
    {"ticker": "sh603171", "name": "税友股份", "market": "CN", "theme": "财税IT/AI应用", "profile": "emerging", "description": "财税信息化和SaaS服务商，关注AI在财税场景的落地。"},
    {"ticker": "sh603918", "name": "金桥信息", "market": "CN", "theme": "AI会议/政企数字化", "profile": "emerging", "description": "政企多媒体通信、智慧会议和数字化解决方案公司。"},
    {"ticker": "sz002777", "name": "久远银海", "market": "CN", "theme": "医疗医保IT/信创", "profile": "emerging", "description": "医保、医疗和民生信息化软件公司，受益医疗数据和政务IT升级。"},
    {"ticker": "sz002368", "name": "太极股份", "market": "CN", "theme": "政务云/信创", "profile": "core", "description": "政务云、行业数字化和信创集成服务商。"},
    {"ticker": "sz000977", "name": "浪潮信息", "market": "CN", "theme": "AI服务器/算力", "profile": "core", "description": "服务器和AI算力基础设施厂商，受益数据中心和国产算力需求。"},
    {"ticker": "sh601138", "name": "工业富联", "market": "CN", "theme": "AI服务器/制造", "profile": "mega", "description": "电子制造和云计算设备平台，覆盖AI服务器、网络设备和精密制造。"},
    {"ticker": "sh603296", "name": "华勤技术", "market": "CN", "theme": "AI终端/ODM", "profile": "core", "description": "智能终端ODM平台，覆盖手机、PC、智能硬件和AI终端制造。"},
    {"ticker": "sh603893", "name": "瑞芯微", "market": "CN", "theme": "端侧AI芯片", "profile": "emerging", "description": "AIoT SoC和端侧AI芯片厂商，覆盖机器视觉、车载、工业和智能终端。"},
    {"ticker": "sh603068", "name": "博通集成", "market": "CN", "theme": "无线连接芯片", "profile": "emerging", "description": "无线连接和物联网芯片设计公司，覆盖蓝牙、WiFi、ETC和智能终端。"},
    {"ticker": "sz002859", "name": "洁美科技", "market": "CN", "theme": "电子材料/被动元件", "profile": "emerging", "description": "电子元器件薄型载带和离型膜供应商，受益消费电子和被动元件复苏。"},
    {"ticker": "sh603678", "name": "火炬电子", "market": "CN", "theme": "军工电子/MLCC", "profile": "emerging", "description": "陶瓷电容和新材料业务，军工电子和高可靠元件属性较强。"},
    {"ticker": "sh603738", "name": "泰晶科技", "market": "CN", "theme": "晶振/电子元件", "profile": "emerging", "description": "石英晶体谐振器和频控器件供应商，关联通信、汽车电子和物联网。"},
    {"ticker": "sz002138", "name": "顺络电子", "market": "CN", "theme": "被动元件/汽车电子", "profile": "core", "description": "电感、磁性器件和被动元件平台，覆盖汽车电子、通信和消费电子。"},
    {"ticker": "sz002384", "name": "东山精密", "market": "CN", "theme": "FPC/光模块/新能源", "profile": "core", "description": "FPC、精密制造和光通信相关业务，覆盖消费电子、AI硬件和新能源车。"},
    {"ticker": "sz002600", "name": "领益智造", "market": "CN", "theme": "AI终端/精密制造", "profile": "core", "description": "消费电子精密结构件和功能件平台，关注AI终端和机器人零部件扩展。"},
    {"ticker": "sh603626", "name": "科森科技", "market": "CN", "theme": "消费电子/机器人结构件", "profile": "emerging", "description": "精密金属结构件和消费电子零部件厂商，具备机器人链条主题弹性。"},
    {"ticker": "sh603595", "name": "东尼电子", "market": "CN", "theme": "电子材料/消费电子", "profile": "emerging", "description": "超微细合金线材、无线充电和电子材料公司，关注消费电子复苏弹性。"},
    {"ticker": "sz002837", "name": "英维克", "market": "CN", "theme": "数据中心液冷/储能温控", "profile": "core", "description": "数据中心、储能和通信设备温控公司，受益AI服务器液冷和储能温控需求。"},
    {"ticker": "sh603279", "name": "景津装备", "market": "CN", "theme": "工业装备/环保设备", "profile": "emerging", "description": "压滤机和环保分离装备龙头，关联矿山、化工和制造业资本开支。"},
    {"ticker": "sz002353", "name": "杰瑞股份", "market": "CN", "theme": "油服/能源装备", "profile": "core", "description": "油气设备和油服平台，受益原油资本开支、海外油服和天然气装备需求。"},
    {"ticker": "sh600968", "name": "海油发展", "market": "CN", "theme": "油服/海工", "profile": "core", "description": "海上油气生产服务、能源技术和海工服务公司，关联油价和海上资本开支。"},
    {"ticker": "sh600026", "name": "中远海能", "market": "CN", "theme": "油运/地缘原油", "profile": "core", "description": "油轮运输平台，受益原油贸易路线变化、运价周期和地缘风险溢价。"},
    {"ticker": "sh601872", "name": "招商轮船", "market": "CN", "theme": "油运/LNG运输", "profile": "core", "description": "油轮、散货和LNG运输平台，关注霍尔木兹、原油贸易和航运景气。"},
    {"ticker": "sz000975", "name": "山金国际", "market": "CN", "theme": "黄金/避险", "profile": "core", "description": "黄金和有色金属矿业公司，受益避险情绪和金价周期。"},
    {"ticker": "sh600489", "name": "中金黄金", "market": "CN", "theme": "黄金/避险", "profile": "core", "description": "黄金矿业平台，关联黄金价格、美元利率和地缘风险。"},
    {"ticker": "sh600547", "name": "山东黄金", "market": "CN", "theme": "黄金/避险", "profile": "core", "description": "黄金采选龙头之一，受益金价和避险需求。"},
    {"ticker": "sz002171", "name": "楚江新材", "market": "CN", "theme": "铜基材料/军工新材料", "profile": "emerging", "description": "铜基材料、碳纤维复材和军工新材料公司，关联铜价、电子材料和高端装备。"},
    {"ticker": "sh601137", "name": "博威合金", "market": "CN", "theme": "铜合金/高速连接材料", "profile": "emerging", "description": "高性能铜合金和精密材料供应商，服务连接器、半导体和新能源。"},
    {"ticker": "sz000988", "name": "华工科技", "market": "CN", "theme": "激光/光模块/传感", "profile": "core", "description": "激光装备、光通信器件和传感业务平台，关联AI光通信和智能制造。"},
    {"ticker": "sz002281", "name": "光迅科技", "market": "CN", "theme": "光模块/光器件", "profile": "core", "description": "光通信器件和模块供应商，受益AI数据中心、交换机和通信网络升级。"},
    {"ticker": "sz301310", "name": "鑫宏业", "market": "CN", "theme": "机器人/线缆", "profile": "emerging"},
    {"ticker": "sz301596", "name": "瑞迪智驱", "market": "CN", "theme": "机器人/传动", "profile": "emerging"},
    {"ticker": "sh688160", "name": "步科股份", "market": "CN", "theme": "机器人控制", "profile": "emerging"},
    {"ticker": "sz300124", "name": "汇川技术", "market": "CN", "theme": "工业自动化/机器人", "profile": "core"},
    {"ticker": "sz300033", "name": "同花顺", "market": "CN", "theme": "AI金融应用", "profile": "core"},
    {"ticker": "sz300803", "name": "指南针", "market": "CN", "theme": "AI金融应用", "profile": "emerging"},
    {"ticker": "ASTS", "name": "AST SpaceMobile", "market": "US", "theme": "卫星通信", "profile": "emerging"},
    {"ticker": "AXTI", "name": "AXT", "market": "US", "theme": "化合物半导体材料", "profile": "emerging"},
    {"ticker": "BB", "name": "BlackBerry", "market": "US", "theme": "车载软件/网络安全", "profile": "emerging"},
    {"ticker": "NOK", "name": "诺基亚", "market": "US", "theme": "通信设备/AI-RAN", "profile": "emerging"},
    {"ticker": "RKLB", "name": "Rocket Lab", "market": "US", "theme": "航天/火箭", "profile": "emerging"},
    {"ticker": "LUNR", "name": "Intuitive Machines", "market": "US", "theme": "月球商业航天", "profile": "emerging"},
    {"ticker": "ACHR", "name": "Archer Aviation", "market": "US", "theme": "eVTOL", "profile": "emerging"},
    {"ticker": "JOBY", "name": "Joby Aviation", "market": "US", "theme": "eVTOL", "profile": "emerging"},
    {"ticker": "IONQ", "name": "IonQ", "market": "US", "theme": "量子计算", "profile": "emerging"},
    {"ticker": "RGTI", "name": "Rigetti", "market": "US", "theme": "量子计算", "profile": "emerging"},
    {"ticker": "SOUN", "name": "SoundHound AI", "market": "US", "theme": "AI语音应用", "profile": "emerging"},
    {"ticker": "BBAI", "name": "BigBear.ai", "market": "US", "theme": "国防AI", "profile": "emerging"},
    {"ticker": "LAES", "name": "SEALSQ", "market": "US", "theme": "安全芯片/后量子", "profile": "emerging"},
    {"ticker": "ENVX", "name": "Enovix", "market": "US", "theme": "高能量密度电池", "profile": "emerging"},
    {"ticker": "AEHR", "name": "Aehr Test Systems", "market": "US", "theme": "半导体测试/SiC", "profile": "emerging"},
    {"ticker": "AMBA", "name": "Ambarella", "market": "US", "theme": "边缘AI视觉芯片", "profile": "emerging"},
    {"ticker": "INDI", "name": "indie Semiconductor", "market": "US", "theme": "汽车芯片", "profile": "emerging"},
    {"ticker": "HIMX", "name": "奇景光电", "market": "US", "theme": "显示/边缘AI芯片", "profile": "emerging"},
    {"ticker": "MU", "name": "美光科技", "market": "US", "theme": "存储/HBM", "profile": "core"},
    {"ticker": "AMD", "name": "AMD", "market": "US", "theme": "AI芯片", "profile": "core"},
    {"ticker": "NVDA", "name": "英伟达", "market": "US", "theme": "AI算力", "profile": "mega"},
    {"ticker": "AVGO", "name": "博通", "market": "US", "theme": "AI网络/ASIC", "profile": "mega"},
    {"ticker": "TSM", "name": "台积电", "market": "US", "theme": "晶圆代工", "profile": "mega"},
    {"ticker": "LMT", "name": "洛克希德马丁", "market": "US", "theme": "军工", "profile": "defensive"},
    {"ticker": "XOM", "name": "埃克森美孚", "market": "US", "theme": "原油", "profile": "defensive"},
    {"ticker": "OXY", "name": "西方石油", "market": "US", "theme": "原油", "profile": "core"},
]


def _now() -> str:
    return datetime.now().isoformat()


def _json_safe(value: Any) -> Any:
    if isinstance(value, float):
        return value if math.isfinite(value) else None
    if isinstance(value, dict):
        return {str(k): _json_safe(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_json_safe(v) for v in value]
    return value


def _append_jsonl(path: Path, payload: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(_json_safe(payload), ensure_ascii=False) + "\n")


def _read_json(path: Path, default: Any) -> Any:
    if not path.exists():
        return default
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return default


def _write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(_json_safe(payload), ensure_ascii=False, indent=2), encoding="utf-8")


def _read_jsonl_tail(path: Path, limit: int = 20) -> List[Dict[str, Any]]:
    if not path.exists():
        return []
    rows: List[Dict[str, Any]] = []
    try:
        for line in path.read_text(encoding="utf-8").splitlines()[-limit:]:
            if not line.strip():
                continue
            parsed = json.loads(line)
            if isinstance(parsed, dict):
                rows.append(parsed)
    except Exception:
        return rows
    return rows


def as_list(value: Any) -> List[str]:
    if isinstance(value, list):
        return [str(item) for item in value if item]
    if value:
        return [str(value)]
    return []


def _is_buyable_cn_ticker(ticker: str) -> bool:
    value = str(ticker or "").lower()
    return value.startswith(("sh600", "sh601", "sh603", "sh605", "sz000", "sz001", "sz002", "sz003"))


def _value(row: pd.Series, *names: str) -> Optional[float]:
    for name in names:
        if name in row and pd.notna(row[name]):
            try:
                return float(row[name])
            except Exception:
                return None
    return None


class StockPickerService:
    def __init__(self) -> None:
        from investment.data.stock_fetcher import StockFetcher

        self.fetcher = StockFetcher()
        self.last_macrostream_errors: List[str] = []

    @property
    def results_path(self) -> Path:
        return STORAGE_DIR / "results.jsonl"

    @property
    def state_path(self) -> Path:
        return STORAGE_DIR / "state.json"

    @property
    def startup_digests_path(self) -> Path:
        return STORAGE_DIR / "startup_digests.jsonl"

    def analyze(self, markets: Optional[List[str]] = None, limit: int = 8, notes: str = "") -> Dict[str, Any]:
        selected_markets = {item.upper() for item in (markets or ["CN", "US"]) if item.upper() in {"CN", "US"}}
        if not selected_markets:
            selected_markets = {"CN", "US"}
        max_items = max(3, min(int(limit or 8), 20))

        context = self._read_context()
        candidates: List[Dict[str, Any]] = []
        errors: List[Dict[str, str]] = []
        bases: List[Dict[str, str]] = []
        for base in CANDIDATE_POOL:
            if base["market"] not in selected_markets:
                continue
            if base["market"] == "CN" and not _is_buyable_cn_ticker(base["ticker"]):
                continue
            bases.append(base)

        executor = ThreadPoolExecutor(max_workers=SCORE_WORKERS)
        futures = {executor.submit(self._score_candidate, base, context): base for base in bases}
        try:
            for future in as_completed(futures, timeout=SCORE_TIMEOUT_SECONDS):
                base = futures[future]
                try:
                    candidates.append(future.result())
                except Exception as exc:
                    errors.append({"ticker": base["ticker"], "error": str(exc)})
        except TimeoutError:
            pending = [base["ticker"] for future, base in futures.items() if not future.done()]
            for ticker in pending[:20]:
                errors.append({"ticker": ticker, "error": f"score timeout after {SCORE_TIMEOUT_SECONDS}s"})
        finally:
            executor.shutdown(wait=False, cancel_futures=True)

        if not candidates:
            # Last-resort fallback: still return a usable response instead of blocking the UI.
            for base in bases[:max_items]:
                candidates.append(
                    {
                        **base,
                        "score": 50,
                        "action": "观察确认",
                        "entry_plan": "等待行情数据恢复后再确认买点。",
                        "stop_loss": "数据不足时不主动开仓。",
                        "position_hint": "先放入观察池。",
                        "why_now": "行情数据暂不可用，仅作为主题候选。",
                        "reasons": ["主题与用户关注方向匹配"],
                        "risks": ["行情和基本面数据不足"],
                        "evidence_links": [],
                    }
                )

        if selected_markets in ({"US"}, {"CN"}):
            candidates.sort(
                key=lambda item: (
                    1 if item.get("profile") == "emerging" else 0,
                    0 if item.get("profile") in {"mega", "defensive"} else 1,
                    item.get("score", 0),
                ),
                reverse=True,
            )
        else:
            candidates.sort(key=lambda item: item.get("score", 0), reverse=True)
        shortlist = candidates[: max_items * 3]
        recommendations = [
            item for item in shortlist
            if item.get("action") != "回避追高" and not (selected_markets == {"US"} and item.get("profile") in {"mega", "defensive"})
        ][:max_items]
        if len(recommendations) < max_items:
            recommendations.extend(
                item for item in shortlist
                if item not in recommendations and item.get("action") != "回避追高" and item.get("profile") != "mega"
            )
            recommendations = recommendations[:max_items]
        watch_only = [item for item in shortlist if item not in recommendations][:8]
        avoid = [item for item in candidates if item.get("action") == "回避追高"][:8]

        ai_summary = self._ai_summary(
            recommendations=recommendations,
            watch_only=watch_only,
            avoid=avoid,
            context=context,
            notes=notes,
        )
        original_by_ticker = {
            str(item.get("ticker")): item
            for item in [*recommendations, *watch_only, *avoid]
            if item.get("ticker")
        }
        final_recommendations = self._merge_ai_items(ai_summary.get("recommendations"), recommendations, original_by_ticker)
        final_watch_only = self._merge_ai_items(ai_summary.get("watch_only"), watch_only, original_by_ticker)
        final_avoid = self._merge_ai_items(ai_summary.get("avoid"), avoid, original_by_ticker)
        if selected_markets == {"US"}:
            demoted = [item for item in final_recommendations if item.get("profile") in {"mega", "defensive"}]
            final_recommendations = [item for item in final_recommendations if item.get("profile") not in {"mega", "defensive"}]
            final_watch_only = [*demoted, *final_watch_only]
            if len(final_recommendations) < max_items:
                for item in recommendations:
                    if item not in final_recommendations and item.get("profile") == "emerging":
                        final_recommendations.append(item)
                    if len(final_recommendations) >= max_items:
                        break
        if selected_markets == {"CN"} and len(final_recommendations) < max(3, max_items // 2):
            for item in recommendations:
                if item not in final_recommendations and item.get("profile") == "emerging":
                    final_recommendations.append(item)
                if len(final_recommendations) >= max_items:
                    break
        final_recommendations, newly_demoted = self._enforce_risk_filter(final_recommendations, selected_markets)
        final_watch_only = [*newly_demoted, *final_watch_only]
        if len(final_recommendations) < max_items:
            refill: List[Dict[str, Any]] = []
            remaining_watch: List[Dict[str, Any]] = []
            seen = {item.get("ticker") for item in final_recommendations}
            for item in final_watch_only:
                action = str(item.get("action") or "")
                if len(final_recommendations) + len(refill) < max_items and item.get("ticker") not in seen and "回避" not in action:
                    refill.append(item)
                    seen.add(item.get("ticker"))
                else:
                    remaining_watch.append(item)
            final_recommendations = [*final_recommendations, *refill]
            final_watch_only = remaining_watch
        final_recommendations = self._enrich_items(final_recommendations[:max_items])
        final_watch_only = self._enrich_items(final_watch_only[:10])
        final_avoid = self._enrich_items(final_avoid[:10])
        result = {
            "generated_at": _now(),
            "markets": sorted(selected_markets),
            "limit": max_items,
            "notes": notes,
            "summary": ai_summary.get("summary") or self._fallback_summary(recommendations),
            "market_view": ai_summary.get("market_view") or self._fallback_market_view(context),
            "recommendations": final_recommendations[:max_items],
            "watch_only": final_watch_only[:10],
            "avoid": final_avoid[:10],
            "source_context": context,
            "tool_trace": [
                {"type": "data", "name": "候选池", "count": len(CANDIDATE_POOL)},
                {"type": "data", "name": "行情走势评分", "count": len(candidates)},
                {"type": "data", "name": "今日要点/事件缓存", "count": len(context.get("recent_events") or [])},
            ],
            "errors": errors[:10],
        }
        _append_jsonl(self.results_path, result)
        return result

    def _enforce_risk_filter(
        self,
        items: List[Dict[str, Any]],
        selected_markets: set[str],
    ) -> tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
        kept: List[Dict[str, Any]] = []
        demoted: List[Dict[str, Any]] = []
        for item in items:
            action = str(item.get("action") or "")
            change_5d = item.get("change_5d")
            change_20d = item.get("change_20d")
            distance_to_high = item.get("distance_to_high_20d")
            risky_action = "回避" in action or "暂不介入" in action
            cn_chasing = (
                selected_markets == {"CN"}
                and (
                    (isinstance(change_20d, (int, float)) and change_20d > 35)
                    or (isinstance(change_5d, (int, float)) and change_5d > 15)
                    or (
                        isinstance(distance_to_high, (int, float))
                        and isinstance(change_20d, (int, float))
                        and distance_to_high > -0.3
                        and change_20d > 18
                    )
                )
            )
            if risky_action or cn_chasing:
                item = {**item}
                if cn_chasing and not risky_action:
                    item["action"] = "只观察，等待充分回踩"
                    item["risks"] = [*as_list(item.get("risks")), "短期涨幅或位置偏高，当前不适合追。"]
                demoted.append(item)
            else:
                kept.append(item)
        return kept, demoted

    def _merge_ai_items(
        self,
        ai_items: Any,
        fallback_items: List[Dict[str, Any]],
        original_by_ticker: Dict[str, Dict[str, Any]],
    ) -> List[Dict[str, Any]]:
        if not isinstance(ai_items, list) or not ai_items:
            return fallback_items
        merged: List[Dict[str, Any]] = []
        for item in ai_items:
            if not isinstance(item, dict):
                continue
            ticker = str(item.get("ticker") or "")
            original = original_by_ticker.get(ticker, {})
            merged.append({**original, **item})
        return merged or fallback_items

    def _enrich_items(self, items: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        if not items:
            return []
        enriched_by_index: Dict[int, Dict[str, Any]] = {}
        executor = ThreadPoolExecutor(max_workers=min(ENRICH_WORKERS, len(items)))
        futures = {executor.submit(self._enrich_candidate, item): (index, item) for index, item in enumerate(items)}
        try:
            for future in as_completed(futures, timeout=max(ENRICH_TIMEOUT_SECONDS * 3, 12)):
                index, fallback = futures[future]
                try:
                    enriched_by_index[index] = future.result()
                except Exception:
                    enriched_by_index[index] = fallback
        except TimeoutError:
            pass
        finally:
            executor.shutdown(wait=False, cancel_futures=True)
        return [enriched_by_index.get(index, item) for index, item in enumerate(items)]

    def _enrich_candidate(self, item: Dict[str, Any]) -> Dict[str, Any]:
        enriched = dict(item)
        ticker = str(enriched.get("ticker") or "")
        market = str(enriched.get("market") or "")
        name = str(enriched.get("name") or ticker)
        company_description = str(enriched.get("description") or "").strip()
        if not company_description:
            company_description = self._company_description(ticker, market, name, str(enriched.get("theme") or ""))
        fundamentals = self._fundamental_summary(ticker, market)
        news = self._recent_news(ticker, name, market)
        if fundamentals.startswith("财务指标暂不可用") or fundamentals.startswith("财务指标获取失败"):
            fundamentals = self._fundamental_from_news(news) or fundamentals
        enriched["company_description"] = company_description
        enriched["fundamental_summary"] = fundamentals
        enriched["recent_news"] = news
        enriched["why_now"] = self._build_why_now(enriched, fundamentals, news)
        links = as_list(enriched.get("evidence_links"))
        for article in news[:2]:
            link = article.get("link")
            if link:
                links.append({"title": article.get("title"), "url": link})
        enriched["evidence_links"] = links[:5]
        return enriched

    def _company_description(self, ticker: str, market: str, name: str, theme: str) -> str:
        if market == "CN":
            try:
                info = self.fetcher.akshare.get_stock_info(ticker)
                if isinstance(info, dict) and "error" not in info:
                    industry = info.get("行业") or info.get("所属行业") or info.get("行业板块")
                    business = info.get("主营业务") or info.get("经营范围")
                    pieces = [str(item) for item in (industry, business) if item]
                    if pieces:
                        return f"{name}：{'；'.join(pieces)[:180]}。"
            except Exception:
                pass
        return f"{name}属于{theme}方向，需结合最新财报、订单、客户和板块强度确认业务兑现。"

    def _fundamental_summary(self, ticker: str, market: str) -> str:
        try:
            metrics = self._call_with_timeout(
                lambda: self.fetcher.get_key_metrics(ticker),
                timeout=ENRICH_TIMEOUT_SECONDS,
                default={"error": "timeout"},
            )
            if not isinstance(metrics, dict) or metrics.get("error"):
                return "财务指标暂不可用，需以最新财报和交易所公告复核。"
            if market == "CN":
                report_date = metrics.get("report_date") or "最新报告期"
                parts = [
                    f"报告期 {report_date}",
                    f"营收同比 {self._fmt_pct(metrics.get('revenue_yoy'))}",
                    f"净利同比 {self._fmt_pct(metrics.get('profit_yoy'))}",
                    f"ROE {self._fmt_pct(metrics.get('roe'))}",
                    f"毛利率 {self._fmt_pct(metrics.get('gross_margin'))}",
                    f"净利率 {self._fmt_pct(metrics.get('profit_margin'))}",
                    f"资产负债率 {self._fmt_pct(metrics.get('debt_ratio'))}",
                ]
                return "，".join(part for part in parts if "--" not in part) or "财务指标暂不可用，需以最新财报复核。"
            parts = [
                f"PE {self._fmt_num(metrics.get('pe_ratio'))}",
                f"PB {self._fmt_num(metrics.get('pb_ratio'))}",
                f"ROE {self._fmt_pct(metrics.get('roe'))}",
                f"毛利率 {self._fmt_pct(metrics.get('gross_margin'))}",
                f"净利率 {self._fmt_pct(metrics.get('profit_margin'))}",
            ]
            return "，".join(part for part in parts if "--" not in part) or "财务指标暂不可用，需结合最新10-K/10-Q复核。"
        except Exception as exc:
            return f"财务指标获取失败：{str(exc)[:80]}"

    def _recent_news(self, ticker: str, name: str, market: str) -> List[Dict[str, Any]]:
        from investment.data.news_fetcher import get_stock_news

        rows = self._call_with_timeout(
            lambda: get_stock_news(ticker, stock_name=name, market=market, limit=3),
            timeout=ENRICH_TIMEOUT_SECONDS,
            default=[],
        )
        result: List[Dict[str, Any]] = []
        for row in rows[:3]:
            if not isinstance(row, dict):
                continue
            title = str(row.get("title") or "").strip()
            if not title:
                continue
            result.append(
                {
                    "title": title[:120],
                    "source": row.get("source"),
                    "published": row.get("published") or row.get("published_date"),
                    "summary": str(row.get("summary") or "")[:180] or None,
                    "link": row.get("link"),
                }
            )
        return result

    def _fundamental_from_news(self, news: List[Dict[str, Any]]) -> str:
        for article in news:
            text = f"{article.get('title') or ''} {article.get('summary') or ''}"
            if not any(key in text for key in ("一季报", "年报", "半年报", "三季报", "营收", "营业总收入", "净利润", "归母净利润")):
                continue
            snippets = []
            for pattern in (
                r"营业总收入为[^，。；\s]+",
                r"营收[^，。；\s]+",
                r"归母净利润为[^，。；\s]+",
                r"净利润为[^，。；\s]+",
                r"同比[^，。；\s]+",
                r"经营活动现金净流入为[^，。；\s]+",
            ):
                for match in re.findall(pattern, text):
                    if match not in snippets:
                        snippets.append(match)
                    if len(snippets) >= 4:
                        break
                if len(snippets) >= 4:
                    break
            if snippets:
                return "新闻财报口径：" + "，".join(snippets[:4]) + "。"
            return "新闻财报口径：" + text[:120]
        return ""

    def _build_why_now(
        self,
        item: Dict[str, Any],
        fundamentals: str,
        news: List[Dict[str, Any]],
    ) -> str:
        reasons = "；".join(as_list(item.get("reasons"))[:3])
        risks = "；".join(as_list(item.get("risks"))[:2])
        news_title = news[0].get("title") if news else ""
        pieces = [
            f"业务：{item.get('company_description')}",
            f"基本面：{fundamentals}",
        ]
        if reasons:
            pieces.append(f"技术/位置：{reasons}")
        if news_title:
            pieces.append(f"近期催化：{news_title}")
        if risks:
            pieces.append(f"主要风险：{risks}")
        return " ".join(str(piece) for piece in pieces if piece)

    def _fmt_pct(self, value: Any) -> str:
        try:
            if value is None:
                return "--"
            num = float(value)
            if abs(num) <= 1.5:
                num *= 100
            return f"{num:.2f}%"
        except Exception:
            return "--"

    def _fmt_num(self, value: Any) -> str:
        try:
            if value is None:
                return "--"
            return f"{float(value):.2f}"
        except Exception:
            return "--"

    def _call_with_timeout(self, func: Any, timeout: int, default: Any) -> Any:
        executor = ThreadPoolExecutor(max_workers=1)
        future = executor.submit(func)
        try:
            return future.result(timeout=timeout)
        except Exception:
            return default
        finally:
            executor.shutdown(wait=False, cancel_futures=True)

    def read_results(self, limit: int = 20) -> List[Dict[str, Any]]:
        return _read_jsonl_tail(self.results_path, max(1, min(limit, 100)))

    def clear_results(self) -> Dict[str, Any]:
        removed = len(self.read_results(limit=10000))
        if self.results_path.exists():
            self.results_path.unlink()
        return {"removed": removed, "path": str(self.results_path)}

    def startup_digest(self, send_alert: bool = True) -> Dict[str, Any]:
        state = _read_json(self.state_path, {})
        last_ts = float(state.get("last_startup_digest_ts") or 0)
        events = self._fetch_macrostream_recent(limit=80)
        if not events:
            events = self._read_cached_macrostream_events(limit=120)
        new_events = [event for event in events if float(event.get("published_at") or 0) > last_ts]
        if not new_events:
            pending = self._latest_unsent_startup_digest()
            if pending and send_alert:
                text = self._format_startup_digest(str(pending.get("summary") or ""), pending.get("events") or [])
                send_result = self._send_feishu_text(text)
                pending_result = {**pending, "resent_at": _now(), "sent": bool(send_result.get("ok")), "send_result": send_result}
                _append_jsonl(self.startup_digests_path, pending_result)
                return pending_result
            result = {
                "generated_at": _now(),
                "event_count": 0,
                "summary": "离线期间未发现新的 MacroStream 重点事件。",
                "sent": False,
            }
            _append_jsonl(self.startup_digests_path, result)
            return result

        important = self._rank_events(new_events)[:12]
        summary = self._summarize_startup_events(important)
        text = self._format_startup_digest(summary, important)
        send_result = self._send_feishu_text(text) if send_alert else {"ok": False, "skipped": True}
        latest_ts = max(float(event.get("published_at") or 0) for event in events)
        state["last_startup_digest_ts"] = latest_ts
        state["last_startup_digest_at"] = _now()
        _write_json(self.state_path, state)
        result = {
            "generated_at": _now(),
            "event_count": len(new_events),
            "important_count": len(important),
            "summary": summary,
            "events": important,
            "sent": bool(send_result.get("ok")),
            "send_result": send_result,
        }
        _append_jsonl(self.startup_digests_path, result)
        return result

    def _latest_unsent_startup_digest(self) -> Optional[Dict[str, Any]]:
        for item in reversed(_read_jsonl_tail(self.startup_digests_path, 20)):
            if item.get("sent"):
                return None
            if item.get("important_count") and item.get("summary"):
                return item
        return None

    def _score_candidate(self, base: Dict[str, str], context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        quote = self.fetcher.get_quote(base["ticker"])
        history = self.fetcher.get_history(base["ticker"], period="3mo", interval="1d")
        close = self._close_series(history)
        latest = float(close.iloc[-1]) if len(close) else quote.get("price")
        change_5d = self._pct(close, 5)
        change_20d = self._pct(close, 20)
        change_60d = self._pct(close, 60)
        high_20 = float(close.tail(20).max()) if len(close) >= 5 else latest
        low_20 = float(close.tail(20).min()) if len(close) >= 5 else latest
        ma20 = float(close.tail(20).mean()) if len(close) >= 20 else latest
        ma60 = float(close.tail(60).mean()) if len(close) >= 40 else ma20
        daily = close.pct_change().dropna().tail(20)
        volatility = float(daily.std() * 100) if len(daily) else None
        distance_to_high = (latest / high_20 - 1) * 100 if latest and high_20 else None
        distance_to_ma20 = (latest / ma20 - 1) * 100 if latest and ma20 else None
        day_change = quote.get("change_percent")

        score = 50.0
        reasons: List[str] = []
        risks: List[str] = []
        profile = base.get("profile", "")
        catalyst_score = self._catalyst_score(base, context or {})

        if change_20d is not None:
            if 2 <= change_20d <= 18:
                score += 16
                reasons.append("20日趋势向上但未极端加速")
            elif change_20d > 30:
                score -= 20
                risks.append("20日涨幅过大，追高风险高")
            elif change_20d < -12:
                score -= 12
                risks.append("中期趋势仍偏弱")
        if change_5d is not None:
            if -4 <= change_5d <= 8:
                score += 14
                reasons.append("近5日没有明显追高")
            elif change_5d > 15:
                score -= 22
                risks.append("短线涨幅过大")
        if latest and ma20 and latest >= ma20:
            score += 8
            reasons.append("价格站上20日均线")
        if latest and ma60 and latest >= ma60:
            score += 6
            reasons.append("价格站上60日均线")
        if distance_to_high is not None:
            if -12 <= distance_to_high <= -2:
                score += 8
                reasons.append("距20日高点有回撤空间，买点不拥挤")
            elif distance_to_high > -1:
                score -= 8
                risks.append("贴近短期高点，需等回踩")
        if volatility is not None:
            if volatility <= 3.5:
                score += 6
                reasons.append("近20日波动率可控")
            elif volatility > 7:
                score -= 12
                risks.append("波动率偏高")
        if isinstance(day_change, (int, float)) and day_change > 7:
            score -= 15
            risks.append("当日涨幅过大，不适合追")
        if profile == "emerging":
            score += 12
            reasons.append("小众高弹性标的，潜在收益弹性高")
        elif profile == "mega":
            score -= 18
            risks.append("大市值核心票，弹性普通，本页不优先")
        elif profile == "defensive":
            score -= 10
            risks.append("防御属性更强，收益弹性有限")
        if catalyst_score > 0:
            score += catalyst_score
            reasons.append("近期重点事件与主题匹配")

        score = round(max(0, min(score, 100)), 1)
        if score >= 75 and profile == "emerging":
            action = "潜力关注，等确认买点"
        elif score >= 75:
            action = "重点关注回踩低吸"
        elif score >= 62:
            action = "观察确认"
        elif risks and any("追高" in item or "涨幅过大" in item for item in risks):
            action = "回避追高"
        else:
            action = "暂不介入"

        return {
            **base,
            "score": score,
            "action": action,
            "price": quote.get("price") or latest,
            "today_change_percent": day_change,
            "change_5d": self._round(change_5d),
            "change_20d": self._round(change_20d),
            "change_60d": self._round(change_60d),
            "distance_to_high_20d": self._round(distance_to_high),
            "distance_to_ma20": self._round(distance_to_ma20),
            "volatility_20d": self._round(volatility),
            "entry_plan": "等回踩20日线附近企稳，或放量突破后次日不破突破位再考虑。",
            "stop_loss": "跌破20日线且板块同步转弱，或亏损达到5%-8%时退出。",
            "position_hint": "先小仓验证，不在单日大涨后追入。",
            "why_now": "来自统一候选池的趋势、回撤、波动率和新闻偏好综合评分。",
            "reasons": reasons[:5],
            "risks": risks[:5] or ["需继续确认板块强度和成交量。"],
            "evidence_links": [],
        }

    def _close_series(self, history: pd.DataFrame) -> pd.Series:
        if history is None or history.empty:
            return pd.Series(dtype="float64")
        for name in ("Close", "close", "收盘"):
            if name in history.columns:
                return pd.to_numeric(history[name], errors="coerce").dropna()
        return pd.Series(dtype="float64")

    def _pct(self, close: pd.Series, days: int) -> Optional[float]:
        if close is None or len(close) <= days:
            return None
        start = float(close.iloc[-days - 1])
        end = float(close.iloc[-1])
        if not start:
            return None
        return (end / start - 1) * 100

    def _round(self, value: Optional[float]) -> Optional[float]:
        return round(value, 2) if isinstance(value, (int, float)) and math.isfinite(value) else None

    def _catalyst_score(self, base: Dict[str, str], context: Dict[str, Any]) -> float:
        text = json.dumps(context, ensure_ascii=False).lower()
        theme = (base.get("theme") or "").lower()
        ticker = (base.get("ticker") or "").lower()
        keywords = {
            "卫星": ["satellite", "space", "starlink", "卫星", "通信"],
            "航天": ["space", "rocket", "spacex", "launch", "航天", "火箭", "月球"],
            "量子": ["quantum", "量子"],
            "ai": ["ai", "artificial intelligence", "算力", "大模型", "agent"],
            "存储": ["memory", "hbm", "dram", "nand", "存储"],
            "半导体": ["semiconductor", "chip", "sic", "半导体", "芯片"],
            "原油": ["oil", "crude", "hormuz", "iran", "原油", "霍尔木兹", "伊朗"],
            "军工": ["defense", "missile", "military", "军工", "导弹"],
        }
        score = 0.0
        if ticker and ticker in text:
            score += 10
        for key, words in keywords.items():
            if key in theme and any(word in text for word in words):
                score += 8
        return min(score, 18)

    def _read_context(self) -> Dict[str, Any]:
        daily = _read_json(REALTIME_DIR / "daily_key_news.json", {})
        events = _read_jsonl_tail(REALTIME_DIR / "events.jsonl", 12)
        startup = _read_jsonl_tail(self.startup_digests_path, 3)
        return {
            "daily_key_news": daily.get("items", [])[:8] if isinstance(daily, dict) else [],
            "startup_digests": startup,
            "recent_events": [
                {
                    "title": item.get("title"),
                    "summary": item.get("summary"),
                    "channel": item.get("channel"),
                    "source_url": item.get("source_url"),
                }
                for item in events[-12:]
            ],
        }

    def _fetch_macrostream_recent(self, limit: int = 80) -> List[Dict[str, Any]]:
        collected: Dict[str, Dict[str, Any]] = {}
        self.last_macrostream_errors = []
        for content_type, channel in (
            (1, "flashes"),
            (2, "macro"),
            (2, "tech"),
        ):
            options = [{"key": 1, "value": str(content_type)}]
            if content_type == 2:
                options.append({"key": 7, "value": channel})
            payload = {
                "list_option": {
                    "limit": limit,
                    "show_total": True,
                    "options": options,
                }
            }
            metadata = {"ContentType": content_type, "ChannelCode": channel}
            for item in self._request_macrostream(payload):
                event = self._normalize_macrostream_item(item, metadata)
                if event.get("id"):
                    collected[str(event["id"])] = event
        events = list(collected.values())
        events.sort(key=lambda item: float(item.get("published_at") or 0), reverse=True)
        return events

    def _read_cached_macrostream_events(self, limit: int = 120) -> List[Dict[str, Any]]:
        rows = _read_jsonl_tail(REALTIME_DIR / "events.jsonl", limit)
        events: List[Dict[str, Any]] = []
        for item in rows:
            if not isinstance(item, dict):
                continue
            events.append(
                {
                    "id": item.get("id") or f"cached:{item.get('source_id')}",
                    "source_id": item.get("source_id"),
                    "title": item.get("title") or "",
                    "summary": str(item.get("summary") or item.get("content") or "")[:1200],
                    "channel": item.get("channel"),
                    "type": item.get("type"),
                    "published_at": self._parse_time(item.get("published_at") or item.get("published_at_iso")),
                    "source_url": item.get("source_url"),
                }
            )
        events.sort(key=lambda event: float(event.get("published_at") or 0), reverse=True)
        return events

    def _request_macrostream(self, payload: Dict[str, Any]) -> List[Dict[str, Any]]:
        url = "https://api.macrostream.ai/api/user/ListContent"
        headers = {
            "User-Agent": "Mozilla/5.0",
            "Accept": "application/json,text/plain,*/*",
            "Referer": "https://www.macrostream.ai/",
            "Origin": "https://www.macrostream.ai",
        }
        for attempt in range(2):
            try:
                resp = requests.post(url, json=payload, headers=headers, timeout=15)
                if resp.status_code >= 400:
                    self.last_macrostream_errors.append(f"HTTP {resp.status_code}: {resp.text[:120]}")
                    return []
                data = resp.json()
                if isinstance(data, dict) and data.get("code") not in (None, 0):
                    self.last_macrostream_errors.append(str(data.get("message") or data.get("code")))
                    return []
                items = self._find_macrostream_items(data)
                if items:
                    return items
                self.last_macrostream_errors.append("response contained no events")
                return []
            except requests.RequestException as exc:
                if attempt == 0:
                    time.sleep(0.5)
                    continue
                self.last_macrostream_errors.append(str(exc)[:180])
        return []

    def _find_macrostream_items(self, data: Any) -> List[Dict[str, Any]]:
        if isinstance(data, list):
            return [item for item in data if isinstance(item, dict)]
        if not isinstance(data, dict):
            return []
        for key in ("data", "Data", "list", "List", "items", "Items", "records", "Records", "contents", "Contents"):
            value = data.get(key)
            if isinstance(value, list):
                return [item for item in value if isinstance(item, dict)]
            nested = self._find_macrostream_items(value)
            if nested:
                return nested
        return []

    def _normalize_macrostream_item(self, item: Dict[str, Any], payload: Dict[str, Any]) -> Dict[str, Any]:
        source_id = str(item.get("id") or item.get("Id") or item.get("content_id") or item.get("ContentId") or "")
        title = str(item.get("title") or item.get("Title") or item.get("headline") or item.get("Headline") or "")
        summary = str(item.get("summary") or item.get("Summary") or item.get("description") or item.get("Description") or item.get("content") or item.get("Content") or "")
        raw_ts = item.get("published_at") or item.get("PublishedAt") or item.get("publish_time") or item.get("PublishTime") or item.get("created_at") or item.get("CreatedAt")
        published_at = self._parse_time(raw_ts)
        content_type = int(payload.get("ContentType") or 0)
        channel = payload.get("ChannelCode") or ("flashes" if content_type == 1 else "article")
        source_url = f"https://www.macrostream.ai/articles/{source_id}" if content_type == 2 and source_id else "https://www.macrostream.ai/flashes"
        return {
            "id": f"macrostream:{source_id}" if source_id else "",
            "source_id": source_id,
            "title": title,
            "summary": summary[:1200],
            "channel": channel,
            "type": "flash" if content_type == 1 else "article",
            "published_at": published_at,
            "source_url": source_url,
        }

    def _parse_time(self, value: Any) -> float:
        if value is None:
            return time.time()
        if isinstance(value, (int, float)):
            return float(value / 1000 if value > 10_000_000_000 else value)
        text = str(value)
        try:
            return float(text)
        except Exception:
            pass
        try:
            return datetime.fromisoformat(text.replace("Z", "+00:00")).timestamp()
        except Exception:
            return time.time()

    def _rank_events(self, events: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        keywords = [
            "ai", "semiconductor", "chip", "memory", "hbm", "space", "satellite", "rocket", "quantum",
            "iran", "hormuz", "oil", "defense", "ipo", "guidance", "earnings",
            "人工智能", "半导体", "芯片", "存储", "航天", "卫星", "火箭", "量子", "伊朗", "霍尔木兹", "原油", "军工",
        ]
        ranked = []
        for event in events:
            text = f"{event.get('title', '')} {event.get('summary', '')}".lower()
            score = sum(1 for key in keywords if key in text)
            if event.get("type") == "article":
                score += 1
            if score > 0:
                event = dict(event)
                event["importance_score"] = score
                ranked.append(event)
        ranked.sort(key=lambda item: (item.get("importance_score") or 0, item.get("published_at") or 0), reverse=True)
        return ranked or events[:12]

    def _summarize_startup_events(self, events: List[Dict[str, Any]]) -> str:
        if not events:
            return "离线期间没有足够重要的新增事件。"
        try:
            from investment.agents.llm import get_llm_client

            llm = get_llm_client()
            prompt = f"""请用中文总结我离线期间新增的重点市场事件，并说明对美股潜力股选股的影响。
重点关注：AI、半导体、存储、量子、卫星通信、商业航天、军工、伊朗/霍尔木兹/原油。
要求：不要逐条翻译，提炼 4-6 个要点；最后给出今天选股应重点看的方向。

事件:
{json.dumps(events, ensure_ascii=False)[:12000]}"""
            return llm.chat(prompt, system_prompt="你是实时市场事件分析员，输出中文，简洁但有交易含义。", temperature=0.2, max_tokens=1200)
        except Exception:
            titles = [event.get("title") or event.get("summary") for event in events[:6]]
            return "离线期间重点事件：" + "；".join(str(item)[:80] for item in titles if item)

    def _format_startup_digest(self, summary: str, events: List[Dict[str, Any]]) -> str:
        links = "\n".join(
            f"- {event.get('title') or event.get('summary', '')[:40]}\n  {event.get('source_url')}"
            for event in events[:6]
        )
        return f"【启动复盘】离线期间重点事件\n\n{summary}\n\n【原文线索】\n{links}"

    def _send_feishu_text(self, text: str) -> Dict[str, Any]:
        app_id = os.getenv("FEISHU_APP_ID") or os.getenv("LARK_APP_ID")
        app_secret = os.getenv("FEISHU_APP_SECRET") or os.getenv("LARK_APP_SECRET")
        receive_id = os.getenv("FEISHU_RECEIVE_ID") or os.getenv("LARK_RECEIVE_ID")
        receive_id_type = os.getenv("FEISHU_RECEIVE_ID_TYPE") or os.getenv("LARK_RECEIVE_ID_TYPE") or "user_id"
        webhook = os.getenv("FEISHU_WEBHOOK_URL") or os.getenv("LARK_WEBHOOK_URL")
        try:
            if webhook:
                resp = requests.post(webhook, json={"msg_type": "text", "content": {"text": text}}, timeout=15)
                return {"ok": resp.status_code < 400, "transport": "webhook", "status_code": resp.status_code, "text": resp.text[:500]}
            if not (app_id and app_secret and receive_id):
                return {"ok": False, "reason": "feishu env not configured"}
            token_resp = requests.post(
                "https://open.feishu.cn/open-apis/auth/v3/tenant_access_token/internal",
                json={"app_id": app_id, "app_secret": app_secret},
                timeout=15,
            )
            token_data = token_resp.json()
            token = token_data.get("tenant_access_token")
            if not token:
                return {"ok": False, "transport": "rest", "error": token_data}
            send_resp = requests.post(
                f"https://open.feishu.cn/open-apis/im/v1/messages?receive_id_type={receive_id_type}",
                headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json; charset=utf-8"},
                json={"receive_id": receive_id, "msg_type": "text", "content": json.dumps({"text": text}, ensure_ascii=False)},
                timeout=15,
            )
            data = send_resp.json()
            return {"ok": send_resp.status_code < 400 and data.get("code") == 0, "transport": "rest", "status_code": send_resp.status_code, "response": data}
        except Exception as exc:
            return {"ok": False, "error": str(exc)}

    def _ai_summary(
        self,
        recommendations: List[Dict[str, Any]],
        watch_only: List[Dict[str, Any]],
        avoid: List[Dict[str, Any]],
        context: Dict[str, Any],
        notes: str,
    ) -> Dict[str, Any]:
        try:
            from investment.agents.llm import get_llm_client

            llm = get_llm_client()
            prompt = f"""请作为谨慎型选股 Agent，基于候选评分输出 JSON。
目标：选出有潜力、不追高、风险低、确定性更大的标的。A股只推荐普通沪深主板，不推荐科创板 sh688 或创业板 sz300/sz301。美股不要只推荐 NVDA/TSM/XOM 这类普通大票；优先从 ASTS/AXTI/BB/NOK/RKLB/LUNR/IONQ/RGTI/SOUN/BBAI/LAES/ENVX/AEHR/AMBA/INDI/HIMX 这类小众高弹性池里找机会。不要编造数据。每个推荐都必须解释公司做什么、基本面是否支持、近期新闻/事件是否有催化，以及为什么现在不是追高。

候选:
{json.dumps(recommendations, ensure_ascii=False)[:12000]}

只观察:
{json.dumps(watch_only, ensure_ascii=False)[:5000]}

回避:
{json.dumps(avoid, ensure_ascii=False)[:5000]}

今日新闻/事件上下文:
{json.dumps(context, ensure_ascii=False)[:8000]}

用户备注:
{notes}

只返回 JSON:
{{
  "summary": "...",
  "market_view": {{"CN": "...", "US": "..."}},
  "recommendations": [候选数组，可重排但必须保留字段 ticker/name/market/theme/score/action/company_description/fundamental_summary/recent_news/entry_plan/stop_loss/why_now/risks],
  "watch_only": [],
  "avoid": []
}}"""
            text = self._call_with_timeout(
                lambda: llm.chat(
                    prompt,
                    system_prompt="你是偏事件驱动和高回报潜力的谨慎型投资研究员。偏好小众高弹性标的，但必须有事件催化、趋势改善、回撤合理和明确止损；明确回避追高。输出中文。",
                    temperature=0.2,
                    max_tokens=2200,
                ),
                timeout=LLM_TIMEOUT_SECONDS,
                default="{}",
            )
            return self._extract_json(text)
        except Exception:
            return {}

    def _extract_json(self, text: str) -> Dict[str, Any]:
        raw = (text or "").strip()
        if raw.startswith("```"):
            raw = raw.strip("`")
            raw = raw.replace("json\n", "", 1).strip()
        start = raw.find("{")
        end = raw.rfind("}")
        if start >= 0 and end > start:
            raw = raw[start : end + 1]
        try:
            parsed = json.loads(raw)
            return parsed if isinstance(parsed, dict) else {}
        except Exception:
            return {}

    def _fallback_summary(self, recommendations: List[Dict[str, Any]]) -> str:
        if not recommendations:
            return "本轮没有找到兼具趋势、回撤和低波动条件的候选，建议等待。"
        names = "、".join(item.get("name") or item.get("ticker") for item in recommendations[:5])
        return f"本轮偏谨慎筛选，优先关注 {names}。共同特征是相对不追高，并保留明确止损条件。"

    def _fallback_market_view(self, context: Dict[str, Any]) -> Dict[str, str]:
        return {
            "CN": "A股侧重半导体、电子材料、储能等主题的回踩确认机会。",
            "US": "美股优先从小众高弹性的AI应用、量子、卫星通信、商业航天、边缘芯片和地缘原油链里找机会，大票只作为风向标。",
        }


_service: Optional[StockPickerService] = None


def get_stock_picker_service() -> StockPickerService:
    global _service
    if _service is None:
        _service = StockPickerService()
    return _service

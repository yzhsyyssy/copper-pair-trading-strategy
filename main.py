# coding=utf-8
from __future__ import print_function, absolute_import, unicode_literals
from gm.api import *

import datetime
import numpy as np
import pandas as pd

def init(context):
    # 选择的两个合约
    context.contract_A = 'INE.BC'  # 国际铜
    context.contract_B = 'SHFE.CU'  # 上海铜
    context.main_contract_A = None  # 主力合约
    context.main_contract_B = None  # 主力合约
    # 回溯周期, 默认20个bar
    context.periods_time = 25     #(可选24-30)
    
    # 不同时间段的bar数量配置
    context.periods_config = {
        '2020-11-19_2021-11-19': 24,   
        '2021-11-20_2022-11-19': 30,   
        '2022-11-20_2023-11-19': 30,    
        '2023-11-20_2024-11-19': 30,
        '2024-11-20_2025-04-30': 24,
    }
    
    # 清仓信号
    context.close_all = False
    # 用于跟踪斜率差的正负变化
    context.slope_sign_history = []
    # 持仓记录
    context.positions = []
    # 上次开仓方向
    context.last_open_sign = None
    # 累计收益历史，用于每日添加
    context.daily_pnl = []
    # 数据一次性获取
    if context.mode == MODE_BACKTEST:
        main_contract_A_list = fut_get_continuous_contracts(csymbol=context.contract_A, start_date=context.backtest_start_time[:10], end_date=context.backtest_end_time[:10])
        main_contract_B_list = fut_get_continuous_contracts(csymbol=context.contract_B, start_date=context.backtest_start_time[:10], end_date=context.backtest_end_time[:10])
        if len(main_contract_A_list) > 0:
            context.main_contract_A_list = {dic['trade_date']: dic['symbol'] for dic in main_contract_A_list}
        if len(main_contract_B_list) > 0:
            context.main_contract_B_list = {dic['trade_date']: dic['symbol'] for dic in main_contract_B_list}
    # 设置定时任务：夜盘21点开始，日盘9点开始
    schedule(schedule_func=algo, date_rule='1d', time_rule='21:00:00')

def calc_slope(prices):
    """计算价格序列的线性回归斜率"""
    if len(prices) < 2:
        return 0
    x = np.arange(len(prices))
    y = prices
    slope, intercept = np.polyfit(x, y, 1)
    return round(slope, 2)  # 保留两位小数

def algo(context):
    now_str = context.now.strftime('%Y-%m-%d')
    # 主力合约
    if context.now.hour > 15:
        date = get_next_n_trading_dates(exchange='SHSE', date=now_str, n=1)[0]
    else:
        date = context.now.strftime('%Y-%m-%d')
    if context.mode == MODE_BACKTEST and date in context.main_contract_A_list and date in context.main_contract_B_list:
        main_contract_A = context.main_contract_A_list[date]
        main_contract_B = context.main_contract_B_list[date]
    else:
        main_contract_A = fut_get_continuous_contracts(csymbol=context.contract_A, start_date=date, end_date=date)[0]['symbol']
        main_contract_B = fut_get_continuous_contracts(csymbol=context.contract_B, start_date=date, end_date=date)[0]['symbol']

    # 有持仓时，检查持仓的合约是否为主力合约, 非主力合约则卖出
    Account_positions = get_position()
    if main_contract_A != context.main_contract_A or main_contract_B != context.main_contract_B:
        if Account_positions:
            for posi in Account_positions:
                if context.main_contract_A == posi['symbol'] and main_contract_A != context.main_contract_A:
                    print('{}：持仓合约由{}替换为主力合约{}'.format(context.now, posi['symbol'], main_contract_A))
                    context.close_all = True
                if context.main_contract_B == posi['symbol'] and main_contract_B != context.main_contract_B:
                    print('{}：持仓合约由{}替换为主力合约{}'.format(context.now, posi['symbol'], main_contract_B))
                    context.close_all = True
        # 更新主力合约
        context.main_contract_A = main_contract_A
        context.main_contract_B = main_contract_B

    # 打印当前持仓情况
    current_positions = get_position()
    if current_positions:
        print(f"{context.now}: 当前持仓详情:")
        for pos in current_positions:
            print(f"  合约: {pos['symbol']}, 方向: {'多' if pos['side'] == PositionSide_Long else '空'}, "
                  f"数量: {pos['volume']}, 成本: {round(pos['vwap'], 2)}")
    else:
        print(f"{context.now}: 当前无持仓")

    # 当context.close_all为True时，清仓
    if context.close_all:
        context.close_all = False
        order_close_all()
        print('{}:平仓'.format(context.now))
        context.slope_sign_history = []
        context.positions = []
        context.last_open_sign = None  # 记录最后一次开仓的斜率差方向
        context.daily_pnl = []  # 清空日收益记录

    # 根据当前日期设置context.periods_time
    current_date = context.now.strftime('%Y-%m-%d')
    # 遍历配置查找匹配的时间段
    for date_range, pt in context.periods_config.items():
        start_date, end_date = date_range.split('_')
        if start_date <= current_date <= end_date:
            context.periods_time = pt
            break
    
    print(f"{context.now}: 当前使用的bar数量: {context.periods_time}")

    # 数据提取
    close_A = history_n(symbol=context.main_contract_A, frequency='1d', count=context.periods_time + 1, end_time=context.now, df=True)['close']
    close_B = history_n(symbol=context.main_contract_B, frequency='1d', count=context.periods_time + 1, end_time=context.now, df=True)['close']

    # 确保数据长度足够
    if len(close_A) < 2 or len(close_B) < 2:
        print(f'{context.now}: 数据不足，不进行交易')
        return

    # 计算斜率：国际铜与上海铜的斜率差
    slope_A = calc_slope(close_A)
    slope_B = calc_slope(close_B)
    slope_diff = slope_A - slope_B

    print(f'{context.now}: 国际铜斜率: {slope_A}, 上海铜斜率: {slope_B}, 斜率差: {slope_diff}')

    # 开仓逻辑
    if not context.positions:  # 如果没有持仓
        current_sign = 1 if slope_diff > 0 else -1 if slope_diff < 0 else 0
        
        if context.last_open_sign is None or (
            (context.last_open_sign > 0 and current_sign < 0) or 
            (context.last_open_sign < 0 and current_sign > 0)
        ):
            if slope_diff > 0:
                # 做多国际铜，做空上海铜
                print('{}:做多国际铜，做空上海铜'.format(context.now))
                price_A = current(symbols=context.main_contract_A)[0]['price']
                price_B = current(symbols=context.main_contract_B)[0]['price']
                order_value(symbol=context.main_contract_A, value=500000, side=OrderSide_Buy, order_type=OrderType_Limit, price=price_A, position_effect=PositionEffect_Open)
                order_value(symbol=context.main_contract_B, value=500000, side=OrderSide_Sell, order_type=OrderType_Limit, price=price_B, position_effect=PositionEffect_Open)
                context.positions = [{'A': 'long', 'B': 'short'}]
                context.last_open_sign = 1  # 记录开仓方向
            elif slope_diff < 0:
                # 做空国际铜，做多上海铜
                print('{}:做空国际铜，做多上海铜'.format(context.now))
                price_A = current(symbols=context.main_contract_A)[0]['price']
                price_B = current(symbols=context.main_contract_B)[0]['price']
                order_value(symbol=context.main_contract_A, value=500000, side=OrderSide_Sell, order_type=OrderType_Limit, price=price_A, position_effect=PositionEffect_Open)
                order_value(symbol=context.main_contract_B, value=500000, side=OrderSide_Buy, order_type=OrderType_Limit, price=price_B, position_effect=PositionEffect_Open)
                context.positions = [{'A': 'short', 'B': 'long'}]
                context.last_open_sign = -1  # 记录开仓方向

    # 平仓逻辑
    current_sign = 1 if slope_diff > 0 else -1 if slope_diff < 0 else 0
    context.slope_sign_history.append(current_sign)
    
    if context.positions:  # 如果有持仓
        # 每天计算当前日收益
        pnl = 0
        for pos in context.positions:
            if pos['A'] == 'long':
                pnl += close_A.iloc[-1] - close_A.iloc[-2]
            elif pos['A'] == 'short':
                pnl += close_A.iloc[-2] - close_A.iloc[-1]
            if pos['B'] == 'long':
                pnl += close_B.iloc[-2] - close_B.iloc[-1]  # 注意，这里是相反的，因为我们做空B
            elif pos['B'] == 'short':
                pnl += close_B.iloc[-1] - close_B.iloc[-2]  # 注意，这里是相反的，因为我们做空B

        pnl_percentage = pnl / (close_A.iloc[-1] + close_B.iloc[-1]) * 2  # 这里的2是因为我们交易了两个合约
        context.daily_pnl.append(pnl_percentage)  # 记录每日收益

        # 每日收益或亏损打印
        if pnl_percentage >= 0:
            print(f'{context.now}: 每日收益:{round(pnl_percentage, 4)}')
        else:
            print(f'{context.now}: 每日亏损:{round(pnl_percentage, 4)}')

        # 每日亏损止损
        if pnl_percentage < -0.01:  # 如果亏损大于0.01
            order_close_all()
            print(f'{context.now}:平仓, 因当前日亏损:{pnl_percentage}')
            context.slope_sign_history = []
            context.positions = []
            context.daily_pnl = []

        # 严格统计连续三日斜率差正负不变的累计收益
        if len(context.slope_sign_history) >= 3:
            if all(s == context.slope_sign_history[0] for s in context.slope_sign_history[-3:]):
                # 计算三日累计收益
                pnl_cumulative = sum(context.daily_pnl[-3:])  # 计算过去3天的累计收益
                
                # 打印累计收益，无论是否执行平仓
                if pnl_cumulative >= 0:
                    print(f'{context.now}: 连续三天斜率差未变, 三日累计收益:{round(pnl_cumulative, 4)}')
                else:
                    print(f'{context.now}: 连续三天斜率差未变, 三日累计亏损:{round(pnl_cumulative, 4)}')

                if pnl_cumulative > 0.005:
                    order_close_all()
                    print(f'{context.now}:平仓, 因三日累计收益大于0.005:{round(pnl_cumulative, 4)}')
                    context.slope_sign_history = []
                    context.positions = []
                    context.daily_pnl = []

        # 斜率方向发生改变时平仓并立即开仓
        if context.last_open_sign is not None and (
            (context.last_open_sign > 0 and current_sign < 0) or 
            (context.last_open_sign < 0 and current_sign > 0)
        ):
            order_close_all()
            print(f'{context.now}:平仓, 因斜率方向改变')
            context.slope_sign_history = []
            context.positions = []
            context.daily_pnl = []
            # 直接调用开仓逻辑
            context.last_open_sign = None  # 重置开仓方向以触发开仓逻辑
            algo(context)  # 递归调用以立即执行开仓逻辑

def on_backtest_finished(context, indicator):
    print('*'*50)
    print('回测已完成，请通过右上角"回测历史"功能查询详情。')

if __name__ == '__main__':
    backtest_start_time = '2020-11-19 00:00:00'  # 自定义回测开始时间
    backtest_end_time = '2025-04-30 00:00:00'  # 自定义回测结束时间

    run(strategy_id='strategy_id',
        filename='main.py',
        mode=MODE_BACKTEST,
        token='{{token}}',
        backtest_start_time=backtest_start_time,
        backtest_end_time=backtest_end_time,
        backtest_adjust=ADJUST_PREV,
        backtest_initial_cash=2000000,
        backtest_commission_ratio=0.0001,
        backtest_slippage_ratio=0.0001,
        backtest_match_mode=1)
from numpy import float64
from vnpy_novastrategy import (
    StrategyTemplate,
    BarData, TickData,
    TradeData, OrderData,
    ArrayManager, Interval,
    Parameter, Variable,
    datetime
)


class DMAVolatilityStrategy(StrategyTemplate):

    author: str = "224040118"

    rsi_length: int = Parameter(14)
    rsi_upper: int = Parameter(60)
    rsi_lower: int = Parameter(40)
    ema_fast: int = Parameter(12)
    ema_slow: int = Parameter(26)
    macd_fast: int = Parameter(12)
    macd_slow: int = Parameter(26)
    macd_signal: int = Parameter(9)
    atr_period: int = Parameter(14)
    atr_multiplier: float = Parameter(2.0)
    bb_length: int = Parameter(20)
    bb_mult: float = Parameter(2.0)
    min_volatility_threshold: float = Parameter(2) # 取值为0.1-5.0
    trading_size: float = Parameter(1)
    test: bool = Parameter(False)

    trading_symbol: str = Variable("")
    rsi: float = Variable(0.0)
    fast_ma: float = Variable(0.0)
    slow_ma: float = Variable(0.0)
    macd_main: float = Variable(0.0)
    macd: float = Variable(0.0)
    macd_hist: float = Variable(0.0)
    bb_upper: float = Variable(0.0)
    bb_lower: float = Variable(0.0)
    trading_target: float = Variable(0.0)
    trading_pos: float = Variable(0.0)

    def on_init(self) -> None:
        """Callback when strategy is inited"""
        self.trading_symbol: str = self.vt_symbols[0]

        self.bar_dt: datetime = None

        self.am: ArrayManager = ArrayManager()

        self.load_bars(100, Interval.MINUTE)

        self.write_log("Strategy is inited.")

    def on_start(self) -> None:
        """Callback when strategy is started"""
        self.write_log("Strategy is started.")

    def on_stop(self) -> None:
        """Callback when strategy is stoped"""
        self.write_log("Strategy is stopped.")

    def on_tick(self, tick: TickData) -> None:
        """Callback of tick data update"""
        self.write_log(tick)
        bar: BarData = tick.extra.get("bar", None)
        if not bar:
            return
        self.write_log(str(bar))

        bar_dt: datetime = bar.datetime
        if self.bar_dt and bar_dt == self.bar_dt:
            return
        self.bar_dt = bar_dt

        bars: dict = {bar.vt_symbol: bar}
        self.on_bars(bars)

    def on_bars(self, bars: dict[str, BarData]) -> None:
        """Callback of candle bar update"""
        self.cancel_all()

        bar: BarData = bars[self.trading_symbol]

        self.am.update_bar(bar)
        if not self.am.inited:
            return
        if len(self.am.close) < max(self.macd_slow, self.bb_length):
            return

        # EMA & MACD
        self.fast_ma = self.am.ema(self.ema_fast)
        self.slow_ma = self.am.ema(self.ema_slow)
        (self.macd_main, self.macd, self.macd_hist) = self.am.macd(fast_period=self.macd_fast,slow_period=self.macd_slow,signal_period=self.macd_signal)

        # Trend
        uptrend = self.fast_ma > self.slow_ma
        downtrend = self.fast_ma < self.slow_ma

        # ATR & BB
        atr_list = self.am.atr(self.atr_period, True).tolist()
        atr_list = atr_list[-50:]
        currentATR = atr_list[-1]
        (self.bb_upper, self.bb_lower) = self.am.boll(self.bb_length, self.bb_mult)

        # Volatility
        historicalATR = sum(atr_list) / len(atr_list)
        atrRatio = currentATR / historicalATR
        vola = ((self.bb_upper - self.bb_lower) / (self.bb_upper + self.bb_lower)) * 200
        isHighVolatility = atrRatio > 0.8 and ((self.bb_upper - self.bb_lower) / (self.bb_upper + self.bb_lower)) * 200 > self.min_volatility_threshold
        
        # Volume

        # Trading Signal
        long_signal = (
            uptrend and                     # 趋势向上
            isHighVolatility                # 波动放大
        )
        short_signal = (
            downtrend and                  # 趋势向下
            isHighVolatility                # 波动放大
        )
        if long_signal:
            self.trading_target = self.trading_size
        elif short_signal:
            self.trading_target = -self.trading_size
        else:
            # 如果没有信号，保持当前仓位
            self.trading_target = self.trading_pos

        trading_volume = self.trading_target - self.trading_pos

        if trading_volume > 0:
            self.buy(self.trading_symbol, bar.close_price * 1.01, abs(trading_volume))
            # print('执行了一次下单')
        else:
            self.short(self.trading_symbol, bar.close_price * 0.99, abs(trading_volume))

        self.put_event()

    def on_trade(self, trade: TradeData) -> None:
        """Callback of trade update"""
        self.trading_pos = self.get_pos(self.trading_symbol)

        self.put_event()

    def on_order(self, order: OrderData) -> None:
        """Callback of order update"""
        pass

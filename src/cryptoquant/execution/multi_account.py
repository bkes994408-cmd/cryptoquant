from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Mapping

from cryptoquant.oms import OMS, OrderStatus
from cryptoquant.risk import KillSwitch

from .binance_gateway import BinanceFuturesOrderGateway, BinanceGatewayConfig, HttpTransport
from .live import LiveOrderAck


@dataclass(frozen=True)
class ExchangeAccountConfig:
    account_id: str
    exchange: str
    api_key: str
    api_secret: str
    base_url: str = "https://fapi.binance.com"
    recv_window_ms: int = 5000


@dataclass(frozen=True)
class MultiAccountOrderRequest:
    account_id: str
    client_order_id: str
    symbol: str
    qty: float


class MultiAccountBinanceGateway:
    """Route order placement to per-account Binance gateways."""

    def __init__(
        self,
        accounts: list[ExchangeAccountConfig],
        *,
        transport: HttpTransport | None = None,
        timestamp_ms_fn: Callable[[], int] | None = None,
    ) -> None:
        if not accounts:
            raise ValueError("accounts must not be empty")

        self._accounts: dict[str, BinanceFuturesOrderGateway] = {}
        for account in accounts:
            if account.exchange.lower() != "binance":
                raise ValueError(f"unsupported exchange={account.exchange}")
            if account.account_id in self._accounts:
                raise ValueError(f"duplicate account_id={account.account_id}")
            self._accounts[account.account_id] = BinanceFuturesOrderGateway(
                BinanceGatewayConfig(
                    api_key=account.api_key,
                    api_secret=account.api_secret,
                    base_url=account.base_url,
                    recv_window_ms=account.recv_window_ms,
                ),
                transport=transport,
                timestamp_ms_fn=timestamp_ms_fn,
            )

    def place_market_order(
        self,
        *,
        account_id: str,
        symbol: str,
        qty: float,
        client_order_id: str,
    ) -> LiveOrderAck:
        gateway = self._accounts.get(account_id)
        if gateway is None:
            raise ValueError(f"unknown account_id={account_id}")
        return gateway.place_market_order(symbol=symbol, qty=qty, client_order_id=client_order_id)

    @property
    def accounts(self) -> tuple[str, ...]:
        return tuple(sorted(self._accounts.keys()))


class MultiAccountLiveExecutor:
    """Live executor with account-aware routing and idempotency scope per account."""

    def __init__(
        self,
        oms_by_account: Mapping[str, OMS],
        gateway: MultiAccountBinanceGateway,
        *,
        kill_switch: KillSwitch | None = None,
    ) -> None:
        if not oms_by_account:
            raise ValueError("oms_by_account must not be empty")

        oms_accounts = set(oms_by_account.keys())
        gateway_accounts = set(gateway.accounts)
        if oms_accounts != gateway_accounts:
            missing_in_oms = sorted(gateway_accounts - oms_accounts)
            missing_in_gateway = sorted(oms_accounts - gateway_accounts)
            raise ValueError(
                "account set mismatch between oms_by_account and gateway: "
                f"missing_in_oms={missing_in_oms}, missing_in_gateway={missing_in_gateway}"
            )

        self._oms_by_account = dict(oms_by_account)
        self._gateway = gateway
        self._kill_switch = kill_switch
        self._acks: dict[tuple[str, str], LiveOrderAck] = {}
        self._request_fingerprint_by_key: dict[tuple[str, str], tuple[str, float]] = {}

    def execute_market(self, req: MultiAccountOrderRequest) -> LiveOrderAck:
        if req.qty == 0:
            raise ValueError("qty must be non-zero")
        if self._kill_switch is not None:
            self._kill_switch.assert_allows_execution()

        cache_key = (req.account_id, req.client_order_id)
        cached = self._acks.get(cache_key)
        req_fingerprint = (req.symbol, req.qty)
        cached_fingerprint = self._request_fingerprint_by_key.get(cache_key)
        if cached is not None:
            if cached_fingerprint != req_fingerprint:
                raise ValueError("conflicting payload for existing account_id + client_order_id")
            return cached

        oms = self._oms_by_account.get(req.account_id)
        if oms is None:
            raise ValueError(f"unknown account_id={req.account_id}")

        scoped_client_order_id = f"{req.account_id}:{req.client_order_id}"
        order = oms.submit(client_order_id=scoped_client_order_id, symbol=req.symbol, qty=req.qty)
        if order.status != OrderStatus.NEW:
            raise ValueError(f"cannot send live order in status={order.status}")

        ack = self._gateway.place_market_order(
            account_id=req.account_id,
            symbol=req.symbol,
            qty=req.qty,
            client_order_id=req.client_order_id,
        )
        self._acks[cache_key] = ack
        self._request_fingerprint_by_key[cache_key] = req_fingerprint
        return ack

    def get_ack(self, account_id: str, client_order_id: str) -> LiveOrderAck | None:
        return self._acks.get((account_id, client_order_id))

    @property
    def accounts(self) -> tuple[str, ...]:
        return tuple(sorted(self._oms_by_account.keys()))

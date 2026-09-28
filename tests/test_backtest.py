import copy
import json
import socket
import ssl
import subprocess
import tempfile
import unittest
import urllib.error
from datetime import datetime, timezone
from pathlib import Path
from tools.backtest import Account, aggregate, benchmark, run, simulate, validate_dataset
from tools.history import fetch_interval, historical_rows
from tools.market import failure_detail
from tools.risk import dec

MINUTE=60000
HOUR=60*MINUTE
START=int(datetime(2026,9,1,tzinfo=timezone.utc).timestamp()*1000)


def config():
    value=json.loads(Path('examples/backtest-assumptions.json').read_text())
    value.update(buy_fee_rate='0',sell_fee_rate='0',spread_rate='0',slippage_rate='0')
    return value


def row(t,o='100',h='101',low='99',c='100'):
    return [t,o,h,low,c,'1','100']


def signal(t=START,maximum='100',stop='98',target='106'):
    return {'signal_close_ms':t,'max_entry_quote':maximum,'stop':stop,'target':target}


def fixture():
    warmup=START-800*HOUR
    h1=[]
    for i in range(800):
        price=dec('100')+dec(i)/100
        h1.append(row(warmup+i*HOUR,str(price),str(price+1),str(price-1),str(price)))
    h1[-2]=row(START-2*HOUR,'102','103','101','102')
    h1[-1]=row(START-HOUR,'110','111','109','110')
    minute=[row(START+i*MINUTE,'109','110','108','109') for i in range(240)]
    minute[1]=row(START+MINUTE,'109','139','108','138')
    h1.extend(aggregate(minute,60))
    return {'schema_version':2,'kind':'bybit_spot_ohlcv','category':'spot','symbol':'BTCUSDT',
            'evaluation_start_ms':START,'evaluation_end_ms':START+4*HOUR,'warmup_start_ms':warmup,
            'execution_interval_minutes':1,'h1':h1,'h4':aggregate(h1,240),'execution':minute}


class SimulationTests(unittest.TestCase):
    def test_target_and_cash_conservation(self):
        bars=[row(START),row(START+MINUTE,h='107')]
        r=simulate([signal()],bars,config(),START,START+2*MINUTE)
        t=r['trades'][0]
        self.assertEqual(t['exit_reason'],'target')
        self.assertEqual(t['entry_price'],100)
        self.assertEqual(t['quantity'],dec('.25'))
        self.assertEqual(t['net_pnl_usdt'],dec('1.5'))
        self.assertEqual(r['ending_equity_usdt'],dec('101.5'))
        self.assertFalse(r['live_eligible'])

    def test_ambiguous_bar_stops_first(self):
        r=simulate([signal()],[row(START,h='107',low='97')],config(),START,START+MINUTE)
        self.assertEqual(r['trades'][0]['exit_reason'],'stop_before_target')
        self.assertEqual(r['total_net_pnl_usdt'],dec('-.5'))

    def test_gap_can_exceed_risk_and_halts_latch(self):
        bars=[row(START),row(START+MINUTE,'90','91','89','90'),row(START+2*MINUTE)]
        r=simulate([signal(),signal(START+2*MINUTE)],bars,config(),START,START+3*MINUTE)
        self.assertEqual(r['trades'][0]['exit_reason'],'gap_stop')
        self.assertEqual(r['total_net_pnl_usdt'],dec('-2.5'))
        self.assertEqual(r['decisions'][-1]['reason'],'account_halt')
        self.assertTrue(r['halt_events'])

    def test_one_position_skips_overlapping_signal(self):
        bars=[row(START),row(START+MINUTE),row(START+2*MINUTE,h='107')]
        r=simulate([signal(),signal(START+MINUTE)],bars,config(),START,START+3*MINUTE)
        self.assertEqual(len(r['trades']),1)
        self.assertEqual(r['decisions'][1]['reason'],'position_already_open')

    def test_time_exit_at_next_bar_open(self):
        bars=[row(START+i*MINUTE) for i in range(721)]
        bars[-1]=row(START+720*MINUTE,'101','102','100','101')
        r=simulate([signal()],bars,config(),START,START+721*MINUTE)
        self.assertEqual(r['trades'][0]['exit_reason'],'time_exit')
        self.assertEqual(r['trades'][0]['exit_price'],101)

    def test_dataset_end_is_not_a_normal_strategy_exit(self):
        r=simulate([signal()],[row(START)],config(),START,START+MINUTE)
        self.assertEqual(r['boundary_liquidations'],1)
        self.assertEqual(r['completed_strategy_trades'],0)
        self.assertIsNone(r['mean_net_r_completed'])

    def test_no_chasing_or_fabricated_entry(self):
        r=simulate([signal()],[row(START,'101','102','100','101')],config(),START,START+MINUTE)
        self.assertEqual(r['trades'],[])
        self.assertEqual(r['decisions'][0]['decision'],'missed')

    def test_costs_and_base_inventory(self):
        p=config();p.update(buy_fee_rate='.001',sell_fee_rate='.001',slippage_rate='.0005')
        r=simulate([signal()],[row(START),row(START+MINUTE,h='107')],p,START,START+2*MINUTE)
        t=r['trades'][0]
        self.assertLess(t['quantity'],t['gross_quantity'])
        self.assertEqual(t['net_pnl_usdt'],t['quantity']*t['exit_price']*dec('.999')-t['cash_spent'])
        self.assertLessEqual(t['initial_risk_usdt'],dec('.5'))

    def test_net_rr_and_minimum_order_rejections(self):
        for sig,p in [(signal(target='101'),config()),(signal(),dict(config(),min_notional='99'))]:
            r=simulate([sig],[row(START)],p,START,START+MINUTE)
            self.assertEqual(r['trades'],[])
            self.assertEqual(r['decisions'][0]['reason'],'risk_or_order_constraint')

    def test_period_resets_use_lagos_and_keep_weekly_halt(self):
        a=Account(dec(100));a.boundary(START,dec(100));a.mark(dec(95),START)
        self.assertTrue(a.day_halted and a.week_halted)
        # 23:00 UTC begins the next Lagos day, not a new week on this fixture date.
        a.boundary(START+23*HOUR,dec(95))
        self.assertFalse(a.day_halted)
        self.assertTrue(a.week_halted)
        self.assertEqual(a.day_start,95)
        monday=int(datetime(2026,9,6,23,tzinfo=timezone.utc).timestamp()*1000)
        a.boundary(monday,dec(95))
        self.assertFalse(a.week_halted)

    def test_intrabar_halt_survives_recovery(self):
        a=Account(dec(100));a.boundary(START,dec(100))
        a.mark(dec(97),START);a.mark(dec(101),START)
        self.assertTrue(a.day_halted)
        self.assertEqual(a.drawdown,3)

    def test_buy_hold_reference(self):
        result=benchmark([row(START),row(START+MINUTE,'106','107','105','106')],config())
        self.assertEqual(result['buy_hold_net_pnl_usdt'],6)


class ExecutionStressTests(unittest.TestCase):
    def model(self, fraction='0.5', delay=1, entry_delay=0):
        return {'entry_delay_ms':entry_delay,'exit_first_fill_fraction':fraction,
                'residual_retry_delay_bars':delay}

    def test_partial_stop_retains_inventory_and_retries_at_later_gap(self):
        bars=[row(START,h='101',low='97'),row(START+MINUTE,'90','91','89','90')]
        r=simulate([signal()],bars,config(),START,START+2*MINUTE,self.model())
        t=r['trades'][0]
        self.assertEqual([f['quantity'] for f in t['exit_fills']],[dec('.125'),dec('.125')])
        self.assertEqual([f['price'] for f in t['exit_fills']],[98,90])
        self.assertEqual(t['exit_reason'],'stop')
        self.assertEqual(t['net_pnl_usdt'],dec('-1.5'))
        self.assertEqual(r['ending_cash_usdt'],dec('98.5'))
        self.assertIsNone(r['unresolved_position'])

    def test_total_first_exit_failure_keeps_exposure_and_blocks_reentry(self):
        bars=[row(START,low='97'),row(START+MINUTE),
              row(START+2*MINUTE,'90','91','89','90')]
        r=simulate([signal(),signal(START+MINUTE)],bars,config(),START,START+3*MINUTE,
                   self.model(fraction='0',delay=2))
        self.assertEqual(r['decisions'][1]['reason'],'position_already_open')
        self.assertEqual(r['trades'][0]['net_pnl_usdt'],dec('-2.5'))
        self.assertEqual(r['trades'][0]['exit_fills'][1]['bar_start_ms'],START+2*MINUTE)
        self.assertTrue(r['halt_events'])

    def test_residual_below_minimum_remains_unsold_with_marked_equity(self):
        bars=[row(START,low='97'),row(START+MINUTE),row(START+2*MINUTE)]
        r=simulate([signal()],bars,config(),START,START+3*MINUTE,self.model(fraction='.9'))
        self.assertEqual(r['trades'],[])
        self.assertEqual(r['unresolved_position']['quantity'],dec('.025'))
        self.assertEqual(r['unresolved_position']['residual_rejections'],2)
        self.assertEqual(r['ending_cash_usdt'],dec('97.05'))
        self.assertEqual(r['unresolved_inventory_mark_usdt'],dec('2.5'))
        self.assertEqual(r['ending_equity_usdt'],dec('99.55'))
        self.assertIsNone(r['mean_net_r_completed'])

    def test_last_bar_partial_fill_does_not_invent_residual_liquidation(self):
        r=simulate([signal()],[row(START,low='97')],config(),START,START+MINUTE,self.model())
        self.assertEqual(r['trades'],[])
        self.assertEqual(r['unresolved_position']['quantity'],dec('.125'))
        self.assertEqual(len(r['unresolved_position']['exit_fills']),1)
        self.assertEqual(r['ending_equity_usdt'],dec('99.75'))

    def test_partial_fills_charge_fees_once_and_preserve_inventory(self):
        p=dict(config(),buy_fee_rate='.001',sell_fee_rate='.001')
        bars=[row(START,low='97'),row(START+MINUTE,'90','91','89','90')]
        r=simulate([signal()],bars,p,START,START+2*MINUTE,self.model())
        t=r['trades'][0]
        self.assertEqual(sum(f['quantity'] for f in t['exit_fills']),t['initial_quantity'])
        net=sum(f['quantity']*f['price']*dec('.999') for f in t['exit_fills'])
        self.assertEqual(t['net_proceeds_usdt'],net)
        self.assertEqual(r['ending_cash_usdt'],dec(100)-t['cash_spent']+net)

    def test_delay_expiry_never_uses_next_bar_to_rescue_entry(self):
        bars=[row(START),row(START+MINUTE,'90','91','89','90')]
        r=simulate([signal()],bars,config(),START,START+2*MINUTE,self.model(entry_delay=60000))
        self.assertEqual(r['trades'],[])
        self.assertEqual(r['decisions'][0]['reason'],'entry_window_expired_by_delay')
        self.assertEqual(r['ending_equity_usdt'],100)

    def test_invalid_and_subminute_scenarios_rejected(self):
        for m in (self.model(fraction='1.1'),self.model(fraction='NaN'),self.model(delay=0),
                  self.model(entry_delay=30000),self.model(entry_delay=True)):
            with self.assertRaises((ValueError,ArithmeticError)):
                simulate([signal()],[row(START)],config(),START,START+MINUTE,m)
        with self.assertRaises(ValueError):
            simulate([signal()],[row(START)],config(),START,START+HOUR,self.model())

    def test_stress_cli_preserves_model_hash(self):
        with tempfile.TemporaryDirectory() as directory:
            base=Path(directory)
            for name,value in [('data',fixture()),('config',config()),('model',self.model())]:
                (base/(name+'.json')).write_text(json.dumps(value))
            result=subprocess.run(['python3','-m','tools.backtest',str(base/'data.json'),
                '--config',str(base/'config.json'),'--execution-model',str(base/'model.json'),
                '--out',str(base/'out.json')],capture_output=True,text=True)
            self.assertEqual(result.returncode,0,result.stderr)
            r=json.loads((base/'out.json').read_text())
            self.assertEqual(len(r['execution_model_sha256']),64)
            self.assertEqual(r['execution_model']['exit_first_fill_fraction'],'0.5')


class DatasetTests(unittest.TestCase):
    def test_end_to_end_signal_to_simulated_trade(self):
        r=run(fixture(),config())
        self.assertEqual(r['mode'],'historical_approximation')
        self.assertEqual(r['completed_strategy_trades'],1)
        self.assertEqual(r['trades'][0]['exit_reason'],'target')
        self.assertTrue(r['limitations'])

    def test_inconsistent_timeframes_rejected(self):
        d=fixture();d['execution'][0][2]='999'
        with self.assertRaises(ValueError):validate_dataset(d)

    def test_missing_execution_bar_rejected(self):
        d=fixture();d['execution'].pop()
        with self.assertRaises(ValueError):validate_dataset(d)

    def test_paginated_history_is_contiguous(self):
        full=[row(START+i*MINUTE) for i in range(4)]
        calls=[]
        def fake(path,params):
            calls.append(params)
            batch=[r for r in full if r[0]<=params['end']][-2:][::-1]
            return {'url':'https://api.bybit.com/v5/market/kline','received_at':'fixture',
                    'sha256':'fixture','response':{'result':{'category':'spot','symbol':'BTCUSDT','list':batch}}}
        rows,pages=fetch_interval(1,START,START+4*MINUTE,fetch=fake,pause=lambda _:None)
        self.assertEqual(rows,full)
        self.assertEqual(len(pages),2)
        self.assertLess(calls[1]['end'],calls[0]['end'])

    def test_duplicate_page_rejected(self):
        def fake(path,params):
            return {'response':{'result':{'category':'spot','symbol':'BTCUSDT','list':[row(START),row(START)]}}}
        with self.assertRaises(ValueError):fetch_interval(1,START,START+MINUTE,fetch=fake)

    def test_cli_report_keeps_provenance_and_separate_journal(self):
        with tempfile.TemporaryDirectory() as directory:
            base=Path(directory); data=base/'dataset.json';conf=base/'config.json';out=base/'result.json'
            data.write_text(json.dumps(fixture()));conf.write_text(json.dumps(config()))
            result=subprocess.run(['python3','-m','tools.backtest',str(data),'--config',str(conf),'--out',str(out)],capture_output=True,text=True)
            self.assertEqual(result.returncode,0,result.stderr)
            report=json.loads(out.read_text())
            self.assertEqual(len(report['dataset_sha256']),64)
            self.assertFalse(report['live_eligible'])
            self.assertTrue(report['code_sha256'])


class DiagnosticTests(unittest.TestCase):
    def test_error_categories(self):
        cases=[(socket.gaierror(-2,'fixture'),'dns'),(ssl.SSLError('fixture'),'tls'),
               (TimeoutError(),'timeout'),(urllib.error.HTTPError('https://api.bybit.com',403,'',{},None),'access_denied'),
               (urllib.error.HTTPError('https://api.bybit.com',429,'',{},None),'rate_limited')]
        for error,kind in cases:
            self.assertEqual(failure_detail(error)[0],kind)
            if isinstance(error,urllib.error.HTTPError): error.close()


if __name__=='__main__': unittest.main()

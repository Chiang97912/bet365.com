# coding:utf-8
import re
import sys
import time
import requests
from requests import request
from autobahn.twisted.websocket import connectWS, WebSocketClientFactory, WebSocketClientProtocol
from autobahn.websocket.compress import (
    PerMessageDeflateOffer,
    PerMessageDeflateResponse,
    PerMessageDeflateResponseAccept,
)
from autobahn.twisted.util import sleep

from twisted.python import log
from twisted.internet.defer import inlineCallbacks, returnValue
from twisted.internet import reactor, ssl
from twisted.internet.protocol import ReconnectingClientFactory

from txaio import start_logging, use_twisted

# use_twisted()

# start_logging(level='debug')
log.startLogging(sys.stdout)
occurred_eventids = []
checklist = {}
language = 'en'  # or cn

headers = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:54.0) Gecko/20100101 Firefox/54.0'
}
ODATA = {}
EV = {}


def toJson(string):
    try:
        dic = {}
        data = string[:-1].split(';')
        for item in data:
            arr = item.split('=')
            dic[arr[0]] = arr[1]
    except Exception as e:
        # print(e)
        pass
    return dic


def dataParse(self, string):
    inPlayDatas = string.split('|CL;')
    basketballDatas = ""
    if len(inPlayDatas) >= 2:
        # soccerDatas = inPlayDatas[1]
        for inPlayData in inPlayDatas:
            if 'ID=18' in inPlayData:
                basketballDatas = inPlayData
                break
    else:
        return  # End generator
    competitions = basketballDatas.split('|CT;')
    if len(competitions) > 0:
        competitions = competitions[1:]
    else:
        competitions = []
    for comp in competitions:
        data = comp.split('|EV;')
        league = toJson(data[0]).get('NA')
        for item in data[1:]:
            MA = toJson(item.split('|MA;')[0])
            eventid = MA['ID'][:8]
            score = MA['SS']
            # print(item.split('|MA;')[0])
            PA0 = item.split('|PA;')[0]
            PA0Json = toJson(PA0)
            TU = PA0Json['TU']
            TT = int(PA0Json['TT'])
            TS = int(PA0Json['TS'])
            TM = int(PA0Json['TM'])
            begints = time.mktime(time.strptime(TU, '%Y%m%d%H%M%S'))
            nowts = time.time() - 8 * 60 * 60
            # The match has not started. TT=0 means the match has not started or paused, TM=45 means in the midfield.
            if TM == 0 and TT == 0:
                retimeset = '00:00'
            else:
                if TT == 1:
                    retimeset = str(int((nowts - begints)/60.0) + TM) + \
                        ':' + str(int((nowts - begints) % 60.0)).zfill(2)
                else:
                    retimeset = '45:00'
            details = item.split('|PA;')[1:]
            if len(details) >= 2:
                hometeam = toJson(details[0]).get('NA')
                awayteam = toJson(details[1]).get('NA')
            else:
                hometeam = ''
                awayteam = ''
            yield league, hometeam, awayteam, score, retimeset, eventid


@inlineCallbacks
def search(league, hometeam, awayteam, score, retimeset, eventid):
    yield sleep(0.3)
    global occurred_eventids
    global checklist
    occurred_eventids.append(eventid)
    checklist[eventid] = {
        'league': league,
        'hometeam': hometeam,
        'awayteam': awayteam,
        'score': score,
        'retimeset': retimeset
    }
    print(league, hometeam, awayteam, score, retimeset, eventid)
    req = u'\x16\x006V{}C18A_1_1\x01'.format(eventid).encode('utf-8')
    returnValue(req)


class MyClientProtocol(WebSocketClientProtocol):
    @inlineCallbacks
    def subscribeGames(self, msg):
        index = 0
        for league, hometeam, awayteam, score, retimeset, eventid in dataParse(self, msg):
            try:
                req = yield search(league, hometeam, awayteam, score, retimeset, eventid)
            except Exception as e:
                print(e)
                self.sendClose(1000)
            else:
                self.sendMessage(req)
            index += 1
            if(index >= 10):
                break

    def updateGameData(self, msg):
        for m in msg.split('|\x08'):
            d = m.split('\x01U|')
            IT = d[0].replace('\x15', '')
            if len(d) > 1 and IT in ODATA.keys():
                dic = toJson(d[1])
                for k in dic.keys():
                    ODATA[IT][k] = dic[k]
                print('update ', IT, dic)

    def newGameDataParse(self, msg):
        data = msg.split('|')
        EVC = {}
        MGC = {}
        MAC = {}
        for item in data:
            if item.startswith('EV;'):
                dic = toJson(item[3:])
                IT = dic.get('IT')
                ODATA[IT] = dic
                EVC = dic
                EVC["ST"] = []
                EVC["MG"] = []
                EV[EVC["FI"]] = EVC
            if item.startswith('ST;'):
                dic = toJson(item[3:])
                EVC["ST"].append(dic)
                IT = dic.get('IT')
                ODATA[IT] = dic
            if(item.startswith('MG;')):
                MGC = toJson(item[3:])
                EVC["MG"].append(MGC)
                MGC["MA"] = []
                IT = dic.get('IT')
                ODATA[IT] = MGC
            if(item.startswith('MA;')):
                MAC = toJson(item[3:])
                MGC["MA"].append(MAC)
                MAC["PA"] = []
                IT = dic.get('IT')
                ODATA[IT] = MAC
            if(item.startswith('PA')):
                dic = toJson(item[3:])
                MAC["PA"].append(dic)
                IT = dic.get('IT')
                ODATA[IT] = dic
        print(len(EV.keys()))
        print(len(ODATA.keys()))

    def sendMessage(self, message):
        print("Send: ", message)
        super().sendMessage(message)

    def onOpen(self):
        req = str('\x23\x03P\x01__time,S_{}\x00'.format(
            self.factory.session_id)).encode('utf-8')
        # print('sending message:', req)
        self.sendMessage(req)

    @inlineCallbacks
    def onMessage(self, payload, isBinary):
        msg = payload.decode('utf-8')
        if msg.startswith('100'):
            if language == 'en':  # English
                req = u'\x16\x00CONFIG_1_3,OVInPlay_1_3,Media_L1_Z3,XL_L1_Z3_C1_W3\x01'.encode(
                    'utf-8')
            elif language == 'cn':  # Chinese
                req = u'\x16\x00CONFIG_10_0,OVInPlay_10_0,Media_L10_Z0,XL_L10_Z0_C1_W3\x01'.encode(
                    'utf-8')
            else:
                req = ''
            self.sendMessage(req)
            req2 = u'\x16\x00OVM5\x01'.encode('utf-8')
            self.sendMessage(req2)

        if language == 'en':  # English
            msg_header = 'OVInPlay_1_3'
        elif language == 'cn':  # Chinese
            msg_header = 'OVInPlay_10_0'

        if msg_header in msg:
            yield self.subscribeGames(msg)
        else:
            matched_id1 = msg.split('F|EV;')[0][-17:-9]
            matched_id2 = msg.split('F|EV;')[0][-16:-8]
            if matched_id1 not in occurred_eventids and matched_id2 not in occurred_eventids:
                self.updateGameData(msg)
            else:
                self.newGameDataParse(msg)


class MyFactory(WebSocketClientFactory, ReconnectingClientFactory):

    def clientConnectionFailed(self, connector, reason):
        self.retry(connector)

    def clientConnectionLost(self, connector, reason):
        self.retry(connector)


def get_session_id():
    url = 'https://www.365365868.com/?&cb=10325517107#/IP/'
    response = requests.get(url=url, headers=headers)
    session_id = response.cookies['pstk']
    return session_id


if __name__ == '__main__':
    USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/69.0.3497.81 Safari/537.36"
    url = 'wss://premws-pt3.365lpodds.com/zap/'

    factory = WebSocketClientFactory(
        url, useragent=USER_AGENT, protocols=['zap-protocol-v1'])
    factory.protocol = MyClientProtocol
    factory.headers = {}

    factory.session_id = get_session_id()

    def accept(response):
        if isinstance(response, PerMessageDeflateResponse):
            return PerMessageDeflateResponseAccept(response)
    factory.setProtocolOptions(perMessageCompressionAccept=accept)
    factory.setProtocolOptions(perMessageCompressionOffers=[PerMessageDeflateOffer(
        accept_max_window_bits=True,
        accept_no_context_takeover=True,
        request_max_window_bits=0,
        request_no_context_takeover=True,
    )])
    # reactor.callFromThread(connectWS, factory)
    # reactor.run()
    if factory.isSecure:
        contextFactory = ssl.ClientContextFactory()
    else:
        contextFactory = None
    connectWS(factory, contextFactory)
    reactor.run()

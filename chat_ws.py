import im.im_pb2 as pb
import requests , json  , websocket  , datetime, logging, random, string
from enum import Enum

class Command(Enum):
    COMMAND_NONE = 0
    SEND_MESSAGE = 1
    FETCH_MESSAGES = 2
    REPORT_ABUSE = 3
    SWITCH_LANGUAGE = 4
    SUBSCRIBE_CHAT = 5
    UNSUBSCRIBE_CHAT = 6
    PING = 7
    FETCH_OTHER_ORDERS = 8
    PUSH_MESSAGE = 100
    USER_STATUS = 200

class chat_ws:
    def __init__(self, iid):
        self.iid = iid
        self.logger = logging.getLogger()
        self.logger.setLevel(logging.INFO)
        #self.logger.info(f"im_chat init iid: {iid}")
        self.req = pb.Request()# 建立proto
        self.chat_id_wrapper = pb.ChatIdsWrapper() # message ChatIDsWrapper
        self.msg_entity = pb.RequestMessageEntity() # message MessageEntity 
    
    def subscribe_chat(self):
        # if len(iids) == 0:
        #     iids.append(self.iid)
        self.req.reqId = str(random.randint(1, 99999))
        self.req.command = Command.SUBSCRIBE_CHAT.value
        # for iid in iids:
        #     self.chat_id_wrapper.chatIds.append(iid)
        self.chat_id_wrapper.chatIds.append(self.iid) # repeated  (iid)
        self.req.data.Pack(self.chat_id_wrapper)        
        return self.req.SerializeToString()

    def send_msg(self , content = ''): #   , content 發送內容
        # if chatId == 0:
        chatId = self.iid
        self.req.reqId = str(random.randint(1, 99999))
        self.req.command = Command.SEND_MESSAGE.value   
        self.msg_entity.contentType  =  1
        self.msg_entity.content = content # 發送內容
        self.msg_entity.chatId =  chatId
        self.msg_entity.iid =  int(chatId)
        self.msg_entity.replyTo = 0        
        self.req.data.Pack(self.msg_entity)
        return self.req.SerializeToString()
    
    def ping(self): 
        self.req.reqId = str(random.randint(1, 99999))
        self.req.command = Command.PING.value
        return self.req.SerializeToString()

    def fetch_old_msg(self, pointer = 0): #  取得舊訊息
        self.req.reqId = str(random.randint(10, 999999))
        self.req.command = Command.FETCH_MESSAGES.value
        fetch_message = pb.FetchArgs()
        fetch_message.chatId = self.iid
        fetch_message.pointer = pointer
        self.req.data.Pack(fetch_message)
        return self.req.SerializeToString()
    
    def get_msg(self, msg):
        try:
            Push  = pb.Push()
            Push.ParseFromString(msg)
            value = Push.data.value # bytes
            return_code = Push.code
            return_msg = ""
            # if Push.command is not Command.PING.value :
            #     self.logger.info(f'reqId: {Push.reqId} , command: {Push.command} , data.value: {value} , code: {return_code } ')
            if Push.command == Command.PUSH_MESSAGE.value :              
                push_msg = pb.PushMessageEntity()
                push_msg.ParseFromString(value)
                return_msg = push_msg.content
            elif Push.command == Command.FETCH_MESSAGES.value :
                old_msgs = pb.PushMessageEntityWrapper()
                old_msgs.ParseFromString(value)
                for msg in old_msgs.pushMessageEntity :
                    return_msg = msg.content  # only return last msg
            
            return return_code , Push.command , return_msg                 

        except Exception as e:
            self.logger.error('error: %s '%e )
            return -1 , -1 , e

if __name__ == "__main__":
    im = chat_ws(iid = "10000")
    msg = im.subscribe_chat()
    print(msg)
    msg = im.send_msg(content = 'test')
    print(msg)
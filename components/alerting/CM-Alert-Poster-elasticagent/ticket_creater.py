import sys
from pathlib import Path
import json
import requests
import yaml
from abc import ABC, abstractmethod

def load_config(config_path='ticket_creater_config.yaml'):
    with open(config_path or Path(__file__).with_name('ticket_creater_config.yaml'), 'r') as file:
        return yaml.safe_load(file)

class ITSMClient:

    def __init__(self, config):
        self.auth_user = config['auth']['user']
        self.auth_pwd = config['auth']['password']
        self.url = config['itsm']['url']

    def send_request(self, json_data):
        data = {'auth_user': self.auth_user, 'auth_pwd': self.auth_pwd, 'json_data': json_data, 'version': 1.0}
        response = requests.post(self.url, data=data)
        print(response.text)

class AlertHandler:

    def __init__(self, config):
        self.config = config
        self.handlers = {'openfile': OpenFileAlert(), 'CPU': CPUAlert(), 'MEM': MEMAlert(), 'Disk': DiskAlert(), 'HostDown': HostDown(), 'WebTCPDown': WebTCPDown(), 'AP_Log': AP_Log(), 'DeepSecurity_Antimalware': DS_AntiMalware(), 'DeepSecurity_Integrity': DS_Integrity(), 'DeepSecurity_intrusion': DeepSecurity_intrusion(), 'DeepSecurity_AgentStatus': DeepSecurity_AgentStatus(), 'Elastic_Agent_Status': Elastic_Agent_Status(), 'NMS_GeneralAlert': NMS_GeneralAlert()}

    def handle_alert(self, param_dict):
        alert_type = param_dict['AlertType']
        if alert_type in self.handlers:
            return self.handlers[alert_type].construct_json(param_dict)
        else:
            raise ValueError(f'Unknown AlertType: {alert_type}')

class AlertStrategy(ABC):

    @abstractmethod
    def construct_json(self, param_dict):
        pass

class OpenFileAlert(AlertStrategy):

    def construct_json(self, param_dict):
        limit = param_dict['Param3']
        hard = param_dict['Param4']
        param_dict['Param1'] = float(param_dict['Param1'])
        Percentage = param_dict['Param1'] * 100
        if int(hard) < int(limit):
            limit = hard
        title = f"[INFRA ELK OpenFile {param_dict['Host']} process:{param_dict['Param5']} {param_dict['AlertType']} over threshold"
        description = {'Hostname': param_dict['Host'], f"{param_dict['AlertType']} usage pct": '%d%%' % Percentage, 'processname': param_dict['Param5'], 'limit': limit, 'fileopen': param_dict['Param2'], 'Time': param_dict['TimeStamp']}
        return self._build_json_data(title, description, param_dict['ITSMCaller'])

    def _build_json_data(self, title, description, caller):
        return json.dumps({'operation': '__CFG_0155__', 'class': 'Incident', 'fields': {'title': title, 'description': json.dumps(description)}, 'caller': caller, 'comment': 'Create by Elastalert', 'output_fields': 'id, ref, title, description'})

class CPUAlert(AlertStrategy):

    def construct_json(self, param_dict):
        param_dict['Param1'] = float(param_dict['Param1'])
        if param_dict['Param1'] < 0.9:
            title = f"[INFRA ELK CPU] {param_dict['Host']} CPU Usage High"
        elif param_dict['Param1'] >= 0.9:
            title = f"[INFRA Emergency CPU] {param_dict['Host']} CPU Usage High"
        else:
            raise ValueError('the cpu parameter %s' % param_dict['Param1'])
        Percentage = param_dict['Param1'] * 100
        description = {'Hostname': param_dict['Host'], 'CPU usage pct': '%f%% ' % Percentage, 'Time': param_dict['TimeStamp']}
        return self._build_json_data(title, description, param_dict['ITSMCaller'])

    def _build_json_data(self, title, description, caller):
        return json.dumps({'operation': '__CFG_0155__', 'class': 'Incident', 'fields': {'title': title, 'description': json.dumps(description)}, 'caller': caller, 'comment': 'Create by Elastalert', 'output_fields': 'id, ref, title, description'})

class MEMAlert(AlertStrategy):

    def construct_json(self, param_dict):
        param_dict['Param1'] = float(param_dict['Param1'])
        if param_dict['Param1'] < 0.9:
            title = f"[INFRA ELK MEM] {param_dict['Host']} Memory Usage High"
        elif param_dict['Param1'] >= 0.9:
            title = f"[INFRA Emergency MEM] {param_dict['Host']} Memory Usage High"
        else:
            raise ValueError('the memory parameter %s' % param_dict['Param1'])
        Percentage = param_dict['Param1'] * 100
        description = {'Hostname': param_dict['Host'], 'MEM usage pct': '%f%% ' % Percentage, 'Time': param_dict['TimeStamp']}
        return self._build_json_data(title, description, param_dict['ITSMCaller'])

    def _build_json_data(self, title, description, caller):
        return json.dumps({'operation': '__CFG_0155__', 'class': 'Incident', 'fields': {'title': title, 'description': json.dumps(description)}, 'caller': caller, 'comment': 'Create by Elastalert', 'output_fields': 'id, ref, title, description'})

class DiskAlert(AlertStrategy):

    def construct_json(self, param_dict):
        param_dict['Param1'] = float(param_dict['Param1'])
        directory = param_dict['Param2'].replace('\\', '/')
        if param_dict['Param1'] < 0.95:
            title = f"[INFRA ELK Disk] {param_dict['Host']} Disk Usage High, Folder: [{directory}]"
        elif param_dict['Param1'] >= 0.95:
            title = f"[INFRA Emergency Disk] {param_dict['Host']} Disk Usage High, Folder: [{directory}]"
        Percentage = param_dict['Param1'] * 100
        description = {'Hostname': param_dict['Host'], 'Disk usage pct': '%s%% ' % Percentage, 'MountPoint': directory, 'Time': param_dict['TimeStamp']}
        return self._build_json_data(title, description, param_dict['ITSMCaller'])

    def _build_json_data(self, title, description, caller):
        return json.dumps({'operation': '__CFG_0155__', 'class': 'Incident', 'fields': {'title': title, 'description': json.dumps(description)}, 'caller': caller, 'comment': 'Create by Elastalert', 'output_fields': 'id, ref, title, description'})

class HostDown(AlertStrategy):

    def construct_json(self, param_dict):
        title = f"[INFRA HOST DOWN] HostName: {param_dict['Host']}"
        ReasonOfDown = param_dict['Param1']
        description = {'Hostname': param_dict['Host'], 'Reason of Host Down': '%s ' % ReasonOfDown, 'Time': param_dict['TimeStamp']}
        return self._build_json_data(title, description, param_dict['ITSMCaller'])

    def _build_json_data(self, title, description, caller):
        return json.dumps({'operation': '__CFG_0155__', 'class': 'Incident', 'fields': {'title': title, 'description': json.dumps(description)}, 'caller': caller, 'comment': 'Create by Elastalert', 'output_fields': 'id, ref, title, description'})

class WebTCPDown(AlertStrategy):

    def construct_json(self, param_dict):
        title = f"[INFRA WEB DOWN] FQDN: {param_dict['Host']}"
        ReasonOfDown = param_dict['Param1']
        description = {'Hostname': param_dict['Host'], 'Reason of WEB Down': '%s ' % ReasonOfDown, 'Time': param_dict['TimeStamp']}
        return self._build_json_data(title, description, param_dict['ITSMCaller'])

    def _build_json_data(self, title, description, caller):
        return json.dumps({'operation': '__CFG_0155__', 'class': 'Incident', 'fields': {'title': title, 'description': json.dumps(description)}, 'caller': caller, 'comment': 'Create by Elastalert', 'output_fields': 'id, ref, title, description'})

class AP_Log(AlertStrategy):

    def construct_json(self, param_dict):
        title = f"[Application Alert] Hostname: {param_dict['Host']}"
        description = {'Hostname': param_dict['Host'], 'Log_Path': '%s' % {param_dict['Param1']}, 'Log_Message': '%s' % {param_dict['Param2']}, 'Time': param_dict['TimeStamp']}
        print('This is APLog')
        return self._build_json_data(title, description, param_dict['ITSMCaller'])

    def _build_json_data(self, title, description, caller):
        return json.dumps({'operation': '__CFG_0155__', 'class': 'Incident', 'fields': {'title': title, 'description': json.dumps(description)}, 'caller': caller, 'comment': 'Create by Elastalert', 'output_fields': 'id, ref, title, description'})

class DS_AntiMalware(AlertStrategy):

    def construct_json(self, param_dict):
        Event_Type = param_dict['Param1']
        MalwareName = param_dict['Param2']
        Date = param_dict['Param3']
        hostname = param_dict['Host']
        title = f'[INFRA DeepSecurity_Event] {hostname} {Event_Type} Critical Event!'
        description = {'Hostname': param_dict['Host'], 'EventType': '%s' % Event_Type, 'MalwareName': '%s' % MalwareName, 'Time': param_dict['TimeStamp']}
        return self._build_json_data(title, description, param_dict['ITSMCaller'])

    def _build_json_data(self, title, description, caller):
        return json.dumps({'operation': '__CFG_0155__', 'class': 'Incident', 'fields': {'title': title, 'description': json.dumps(description)}, 'caller': caller, 'comment': 'Create by Elastalert', 'output_fields': 'id, ref, title, description'})

class DS_Integrity(AlertStrategy):

    def construct_json(self, param_dict):
        Event_Type = param_dict['Param1']
        IntegrityPath = param_dict['Param2']
        IntegrityType = param_dict['Param3']
        Action_Tools = param_dict['Param4']
        hostname = param_dict['Host']
        title = f'[INFRA DeepSecurity_Event] {hostname} {Event_Type} Critical Event!'
        description = {'Hostname': param_dict['Host'], 'EventType': '%s' % Event_Type, 'IntegrityPath': '%s' % IntegrityPath, 'IntegrityType': '%s' % IntegrityType, 'Action_Tools': '%s' % Action_Tools, 'Event_Time': param_dict['TimeStamp']}
        return self._build_json_data(title, description, param_dict['ITSMCaller'])

    def _build_json_data(self, title, description, caller):
        return json.dumps({'operation': '__CFG_0155__', 'class': 'Incident', 'fields': {'title': title, 'description': json.dumps(description)}, 'caller': caller, 'comment': 'Create by Elastalert', 'output_fields': 'id, ref, title, description'})

class DeepSecurity_intrusion(AlertStrategy):

    def construct_json(self, param_dict):
        Event_Type = param_dict['Param1']
        SourceIP = param_dict['Param2']
        SourcePort = param_dict['Param3']
        DestinationIP = param_dict['Param4']
        DestinationPort = param_dict['Param5']
        Action = param_dict['Param6']
        Date = param_dict['Param7']
        hostname = param_dict['Host']
        title = f'[INFRA DeepSecurity_Event] {hostname} {Event_Type} Critical Event!'
        description = {'Hostname': param_dict['Host'], 'EventType': '%s' % Event_Type, 'SourceIP': '%s' % SourceIP, 'SourcePort': '%s' % SourcePort, 'DestinationIP': '%s' % DestinationIP, 'DestinationPort': '%s' % DestinationPort, 'Action': '%s' % Action, 'Time': param_dict['TimeStamp']}
        return self._build_json_data(title, description, param_dict['ITSMCaller'])

    def _build_json_data(self, title, description, caller):
        return json.dumps({'operation': '__CFG_0155__', 'class': 'Incident', 'fields': {'title': title, 'description': json.dumps(description)}, 'caller': caller, 'comment': 'Create by Elastalert', 'output_fields': 'id, ref, title, description'})

class DeepSecurity_AgentStatus(AlertStrategy):

    def construct_json(self, param_dict):
        Event_Type = 'Agent Status Warning'
        AgentStatus = param_dict['Param1']
        AgentStatusMessages = param_dict['Param2']
        hostname = param_dict['Host']
        title = f'[INFRA DeepSecurity_Agent] {hostname} {Event_Type} Critical Event!'
        description = {'Hostname': param_dict['Host'], 'Agent_status': '%s' % AgentStatus, 'AgentStatusMessages': '%s' % AgentStatusMessages, 'Time': param_dict['TimeStamp']}
        return self._build_json_data(title, description, param_dict['ITSMCaller'])

    def _build_json_data(self, title, description, caller):
        return json.dumps({'operation': '__CFG_0155__', 'class': 'Incident', 'fields': {'title': title, 'description': json.dumps(description)}, 'caller': caller, 'comment': 'Create by Elastalert', 'output_fields': 'id, ref, title, description'})

class Elastic_Agent_Status(AlertStrategy):

    def construct_json(self, param_dict):
        status = param_dict['Param1']
        hostname = param_dict['Host']
        title = f'[INFRA Elastic_Agent] {hostname} Status : {status} Event!'
        description = {'Hostname': param_dict['Host'], 'agent_status': status, 'Time': param_dict['TimeStamp']}
        return self._build_json_data(title, description, param_dict['ITSMCaller'])

    def _build_json_data(self, title, description, caller):
        return json.dumps({'operation': '__CFG_0155__', 'class': 'Incident', 'fields': {'title': title, 'description': json.dumps(description)}, 'caller': caller, 'comment': 'Create by Elastalert', 'output_fields': 'id, ref, title, description'})

class NMS_GeneralAlert(AlertStrategy):

    def construct_json(self, param_dict):
        device = param_dict['Host']
        rule_name = param_dict['Param1']
        severity = param_dict['Param2']
        title = f'[Network Device] {device} {rule_name} {severity} Event!'
        description = {'device_ip': param_dict['Param3'], 'location': param_dict['Param4'], 'message': param_dict['Param5'], 'alert_time': param_dict['TimeStamp']}
        return self._build_json_data(title, description, param_dict['ITSMCaller'])

    def _build_json_data(self, title, description, caller):
        return json.dumps({'operation': '__CFG_0155__', 'class': 'Incident', 'fields': {'title': title, 'description': json.dumps(description)}, 'caller': caller, 'comment': 'Create by Elastalert', 'output_fields': 'id, ref, title, description'})

def get_param(index, default=None):
    return sys.argv[index] if len(sys.argv) > index else default

def main():
    config = load_config()
    itsm_client = ITSMClient(config)
    alert_handler = AlertHandler(config)
    param_dict = {'ITSMCaller': get_param(1, 'default_caller'), 'AlertType': get_param(2, 'default_alert_type'), 'Host': get_param(3, 'default_host'), 'TimeStamp': get_param(4, 'default_timestamp'), 'Param1': get_param(5, 'default_param1'), 'Param2': get_param(6, 'default_param2'), 'Param3': get_param(7, 'default_param3'), 'Param4': get_param(8, 'default_param4'), 'Param5': get_param(9, 'default_param5'), 'TEST': False if get_param(2) != 'TEST' else True}
    try:
        json_data = alert_handler.handle_alert(param_dict)
        itsm_client.send_request(json_data)
        print('current alert type is : %s hostname: %s ' % (param_dict['AlertType'], param_dict['Host']))
    except Exception as e:
        print('current alert type is : %s' % param_dict['AlertType'])
        print(f'Error: {e}')
if __name__ == '__main__':
    main()

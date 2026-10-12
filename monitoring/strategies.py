import sys
import json
import requests
import yaml
from abc import ABC, abstractmethod
from datetime import datetime
import pytz
import time

class AlertHandler:

    def __init__(self, config):
        self.config = config
        self.handlers = {'openfile': OpenFileAlert(), 'CPU': CPUAlert(), 'MEM': MEMAlert(), 'Disk': DiskAlert(), 'HostDown': HostDown(), 'WebTCPDown': WebTCPDown(), 'AP_Log': AP_Log(), 'iSCSI_Error': iSCSI_Error(), 'DeepSecurity_Antimalware': DS_AntiMalware(), 'DeepSecurity_Integrity': DS_Integrity(), 'DeepSecurity_intrusion': DeepSecurity_intrusion(), 'DeepSecurity_AgentStatus': DeepSecurity_AgentStatus(), 'Elastic_Agent_Status': Elastic_Agent_Status(), 'APM': APM(), 'SwitchFailover': SwitchFailover(), 'ORACLE_Log': ORACLE_Log(), 'ApplicationSession': ApplicationSession(), 'paloalto': paloalto(), 'NMS_GeneralAlert': NMS_GeneralAlert(), 'DC-CA_RenewAlert': CertificateRenewal(), 'CloseWait_Alert': CloseWait_Alert(), 'Apim_Alert': Apim_Alert(), 'MaxProcess_Alert': MaxProcess_Alert(), 'ApplicationDebug': ApplicationDebug()}

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
        title = f"[INFRA ELK OpenFile] {param_dict['Host']} process:{param_dict['Param5']} {param_dict['AlertType']} over threshold"
        description = {'Hostname': param_dict['Host'], f"{param_dict['AlertType']} usage pct": '%d%%' % Percentage, 'processname': param_dict['Param5'], 'limit': limit, 'fileopen': param_dict['Param2'], 'Time': param_dict['TimeStamp']}
        return self._build_json_data(title, description, param_dict['ITSMCaller'])

    def _build_json_data(self, title, description, caller):
        return json.dumps({'operation': 'core/create', 'class': 'Incident', 'fields': {'title': title, 'description': json.dumps(description)}, 'caller': caller, 'comment': 'Create by Elastalert', 'output_fields': 'id, ref, title, description'})

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
        return json.dumps({'operation': 'core/create', 'class': 'Incident', 'fields': {'title': title, 'description': json.dumps(description)}, 'caller': caller, 'comment': 'Create by Elastalert', 'output_fields': 'id, ref, title, description'})

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
        return json.dumps({'operation': 'core/create', 'class': 'Incident', 'fields': {'title': title, 'description': json.dumps(description)}, 'caller': caller, 'comment': 'Create by Elastalert', 'output_fields': 'id, ref, title, description'})

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
        return json.dumps({'operation': 'core/create', 'class': 'Incident', 'fields': {'title': title, 'description': json.dumps(description)}, 'caller': caller, 'comment': 'Create by Elastalert', 'output_fields': 'id, ref, title, description'})

class HostDown(AlertStrategy):

    def construct_json(self, param_dict):
        title = f"[INFRA HOST DOWN] HostName: {param_dict['Host']}"
        ReasonOfDown = param_dict['Param1']
        description = {'Hostname': param_dict['Host'], 'Reason of Host Down': '%s ' % ReasonOfDown, 'Time': param_dict['TimeStamp']}
        return self._build_json_data(title, description, param_dict['ITSMCaller'])

    def _build_json_data(self, title, description, caller):
        return json.dumps({'operation': 'core/create', 'class': 'Incident', 'fields': {'title': title, 'description': json.dumps(description)}, 'caller': caller, 'comment': 'Create by Elastalert', 'output_fields': 'id, ref, title, description'})

class WebTCPDown(AlertStrategy):

    def construct_json(self, param_dict):
        title = f"[INFRA WEB DOWN] FQDN: {param_dict['Host']}"
        ReasonOfDown = param_dict['Param1']
        description = {'Hostname': param_dict['Host'], 'Reason of WEB Down': '%s ' % ReasonOfDown, 'Time': param_dict['TimeStamp']}
        return self._build_json_data(title, description, param_dict['ITSMCaller'])

    def _build_json_data(self, title, description, caller):
        return json.dumps({'operation': 'core/create', 'class': 'Incident', 'fields': {'title': title, 'description': json.dumps(description)}, 'caller': caller, 'comment': 'Create by Elastalert', 'output_fields': 'id, ref, title, description'})

class AP_Log(AlertStrategy):

    def construct_json(self, param_dict):
        title = f"[Application Alert] Hostname: {param_dict['Host']} LogPath: {param_dict['Param1']}"
        description = {'Hostname': param_dict['Host'], 'Log_Path': '%s' % {param_dict['Param1']}, 'Log_Message': '%s' % {param_dict['Param2']}, 'Time': param_dict['TimeStamp']}
        return self._build_json_data(title, description, param_dict['ITSMCaller'])

    def _build_json_data(self, title, description, caller):
        return json.dumps({'operation': 'core/create', 'class': 'Incident', 'fields': {'title': title, 'description': json.dumps(description)}, 'caller': caller, 'comment': 'Create by Elastalert', 'output_fields': 'id, ref, title, description'})

class ApplicationDebug(AlertStrategy):

    def construct_json(self, param_dict):
        title = f"[Application Alert] Hostname: {param_dict['Host']} LogPath: {param_dict['Param1']}"
        description = {'Hostname': param_dict['Host'], 'Log_Path': '%s' % {param_dict['Param1']}, 'Log_Message': '%s' % {param_dict['Param2']}, 'Time': param_dict['TimeStamp']}
        return self._build_json_data(title, description, param_dict['ITSMCaller'])

    def _build_json_data(self, title, description, caller):
        return json.dumps({'operation': 'core/create', 'class': 'Incident', 'fields': {'title': title, 'description': json.dumps(description)}, 'caller': caller, 'comment': 'Create by Elastalert', 'output_fields': 'id, ref, title, description'})

    def repeat_create(self, param_dict, send_func):
        pass

class MaxProcess_Alert(AlertStrategy):

    def construct_json(self, param_dict):
        title = f"[INFRA ELK MaxProcess] Hostname: {param_dict['Host']} Announce to system manager"
        description = {'Hostname': param_dict['Host'], 'Process_Num': '%s' % param_dict['Param1'], 'User_Name': param_dict.get('Param2', 'N/A'), 'Description': 'Operational event', 'Time': param_dict['TimeStamp']}
        return self._build_json_data(title, description, param_dict['ITSMCaller'])

    def _build_json_data(self, title, description, caller):
        return json.dumps({'operation': 'core/create', 'class': 'Incident', 'fields': {'title': title, 'description': json.dumps(description)}, 'caller': caller, 'comment': 'Create by Elastalert', 'output_fields': 'id, ref, title, description'})

class Apim_Alert(AlertStrategy):

    def construct_json(self, param_dict):
        title = f"[INFRA Apim_Alert] Hostname: {param_dict['Host']}  APIM System Service Status Failure"
        description = {'Hostname': param_dict['Host'], 'Service': param_dict.get('Param1'), 'Status': param_dict.get('Param2'), 'Dp_node_host': param_dict.get('Param3'), 'Dp_sync_status': param_dict.get('Param4'), 'Description': 'Operational event', 'Time': param_dict['TimeStamp']}
        return self._build_json_data(title, description, param_dict['ITSMCaller'])

    def _build_json_data(self, title, description, caller):
        return json.dumps({'operation': 'core/create', 'class': 'Incident', 'fields': {'title': title, 'description': json.dumps(description)}, 'caller': caller, 'comment': 'Create by Elastalert', 'output_fields': 'id, ref, title, description'})

class ApplicationSession(AlertStrategy):

    def construct_json(self, param_dict):
        try:
            local_time_str = param_dict['TimeStamp']
            local_time = datetime.strptime(local_time_str, '%Y-%m-%d %H:%M:%S')
            if 9 <= local_time.hour < 23:
                title = f"[Application Alert] Hostname: {param_dict['Host']} LogPath: {param_dict['Param1']}"
                description = {'Hostname': param_dict['Host'], 'Log_Path': '%s' % {param_dict['Param1']}, 'Log_Message': '%s' % {param_dict['Param2']}, 'Time': local_time_str}
                return self._build_json_data(title, description, param_dict['ITSMCaller'])
            else:
                return None
        except Exception as e:
            return None

    def _build_json_data(self, title, description, caller):
        return json.dumps({'operation': 'core/create', 'class': 'Incident', 'fields': {'title': title, 'description': json.dumps(description)}, 'caller': caller, 'comment': 'Create by Elastalert', 'output_fields': 'id, ref, title, description'})

class SwitchFailover(AlertStrategy):

    def construct_json(self, param_dict):
        title = f"[CentralBankASswitch Alert] Hostname: {param_dict['Host']} Announce to MIS Team"
        description = {'Hostname': param_dict['Host'], 'Log_Message': '%s' % {param_dict['Param1']}, 'Time': param_dict['TimeStamp'], 'Description': 'Operational event'}
        return self._build_json_data(title, description, param_dict['ITSMCaller'])

    def _build_json_data(self, title, description, caller):
        return json.dumps({'operation': 'core/create', 'class': 'Incident', 'fields': {'title': title, 'description': json.dumps(description)}, 'caller': caller, 'comment': 'Create by Elastalert', 'output_fields': 'id, ref, title, description'})

class paloalto(AlertStrategy):

    def construct_json(self, param_dict):
        title = f"[paloalto Alert] Log_Message: {param_dict['Log_Message']} Announce to MIS Team"
        description = {'Log_Message': '%s' % param_dict['Log_Message'], 'Time': param_dict['TimeStamp'], 'Description': 'Operational event'}
        return self._build_json_data(title, description, param_dict['ITSMCaller'])

    def _build_json_data(self, title, description, caller):
        return json.dumps({'operation': 'core/create', 'class': 'Incident', 'fields': {'title': title, 'description': json.dumps(description)}, 'caller': caller, 'comment': 'Create by Elastalert', 'output_fields': 'id, ref, title, description'})

class ORACLE_Log(AlertStrategy):

    def construct_json(self, param_dict):
        title = f"[Oracle Alert] Hostname: {param_dict['Host']} LogPath: {param_dict['Param1']}"
        description = {'Hostname': param_dict['Host'], 'Log_Path': '%s' % {param_dict['Param1']}, 'Log_Message': param_dict['Param2'], 'Time': param_dict['TimeStamp']}
        return self._build_json_data(title, description, param_dict['ITSMCaller'])

    def _build_json_data(self, title, description, caller):
        return json.dumps({'operation': 'core/create', 'class': 'Incident', 'fields': {'title': title, 'description': json.dumps(description)}, 'caller': caller, 'comment': 'Create by Elastalert', 'output_fields': 'id, ref, title, description'})

class CloseWait_Alert(AlertStrategy):

    def construct_json(self, param_dict):
        title = f"[CloseWait Alert] Hostname: {param_dict['Host']} Announce to system manager"
        description = {'Hostname': param_dict['Host'], 'CloseWait_Num': '%s' % {param_dict['Param1']}, 'Time': param_dict['TimeStamp'], 'Description': 'Operational event'}
        return self._build_json_data(title, description, param_dict['ITSMCaller'])

    def _build_json_data(self, title, description, caller):
        return json.dumps({'operation': 'core/create', 'class': 'Incident', 'fields': {'title': title, 'description': json.dumps(description)}, 'caller': caller, 'comment': 'Create by Elastalert', 'output_fields': 'id, ref, title, description'})

class CertificateRenewal(AlertStrategy):

    def construct_json(self, param_dict):
        title = f"Operational event{param_dict['Host']}"
        description = {'Hostname': param_dict['Host'], 'Log_Message': '%s' % {param_dict['Param1']}, 'Time': param_dict['TimeStamp']}
        return self._build_json_data(title, description, param_dict['ITSMCaller'])

    def _build_json_data(self, title, description, caller):
        return json.dumps({'operation': 'core/create', 'class': 'Incident', 'fields': {'title': title, 'description': json.dumps(description)}, 'caller': caller, 'comment': 'Create by Elastalert', 'output_fields': 'id, ref, title, description'})

class iSCSI_Error(AlertStrategy):

    def construct_json(self, param_dict):
        title = f"[!! iSCSI Disconnected Alert !!] Hostname: {param_dict['Host']}"
        description = {'Hostname': param_dict['Host'], 'Log_Message': '%s' % {param_dict['Param1']}, 'Time': param_dict['TimeStamp']}
        return self._build_json_data(title, description, param_dict['ITSMCaller'])

    def _build_json_data(self, title, description, caller):
        return json.dumps({'operation': 'core/create', 'class': 'Incident', 'fields': {'title': title, 'description': json.dumps(description)}, 'caller': caller, 'comment': 'Create by Elastalert', 'output_fields': 'id, ref, title, description'})

class APM(AlertStrategy):

    def construct_json(self, param_dict):
        api_name = param_dict['Param4'].replace(' ', '_') if 'Param4' in param_dict and param_dict['Param4'] else ''
        title = f"[!! APM Alert !!] Service: {param_dict['Param2']} Description: {param_dict['Param3']}"
        description = {'Hostname': param_dict['Host'], 'Duration': '%s' % param_dict['Param1'], 'Time': param_dict['TimeStamp'], 'Service': param_dict['Param2'], 'Description': param_dict['Param3'], 'API_Name': api_name}
        return self._build_json_data(title, description, param_dict['ITSMCaller'])

    def _build_json_data(self, title, description, caller):
        return json.dumps({'operation': 'core/create', 'class': 'Incident', 'fields': {'title': title, 'description': json.dumps(description)}, 'caller': caller, 'comment': 'Create by Elastalert', 'output_fields': 'id, ref, title, description'})

class DS_AntiMalware(AlertStrategy):

    def construct_json(self, param_dict):
        Event_Type = param_dict['Param1']
        MalwareName = param_dict['Param2']
        Date = param_dict['Param3']
        title = f"[INFRA DeepSecurity_Event] {param_dict['Host']} {Event_Type} Critical Event!"
        description = {'Hostname': param_dict['Host'], 'EventType': '%s' % Event_Type, 'MalwareName': '%s' % MalwareName, 'Time': param_dict['TimeStamp']}
        return self._build_json_data(title, description, param_dict['ITSMCaller'])

    def _build_json_data(self, title, description, caller):
        return json.dumps({'operation': 'core/create', 'class': 'Incident', 'fields': {'title': title, 'description': json.dumps(description)}, 'caller': caller, 'comment': 'Create by Elastalert', 'output_fields': 'id, ref, title, description'})

class DS_Integrity(AlertStrategy):

    def construct_json(self, param_dict):
        Event_Type = param_dict['Param1']
        IntegrityPath = param_dict['Param2']
        IntegrityType = param_dict['Param3']
        Action_Tools = param_dict['Param4']
        title = f"[INFRA DeepSecurity_Event] {param_dict['Host']} {Event_Type} Critical Event!"
        description = {'Hostname': param_dict['Host'], 'EventType': '%s' % Event_Type, 'IntegrityPath': '%s' % IntegrityPath, 'IntegrityType': '%s' % IntegrityType, 'Action_Tools': '%s' % Action_Tools, 'Event_Time': param_dict['TimeStamp']}
        return self._build_json_data(title, description, param_dict['ITSMCaller'])

    def _build_json_data(self, title, description, caller):
        return json.dumps({'operation': 'core/create', 'class': 'Incident', 'fields': {'title': title, 'description': json.dumps(description)}, 'caller': caller, 'comment': 'Create by Elastalert', 'output_fields': 'id, ref, title, description'})

class DeepSecurity_intrusion(AlertStrategy):

    def construct_json(self, param_dict):
        Event_Type = param_dict['Param1']
        SourceIP = param_dict['Param2']
        SourcePort = param_dict['Param3']
        DestinationIP = param_dict['Param4']
        DestinationPort = param_dict['Param5']
        Action = param_dict['Param6']
        Date = param_dict['Param7']
        title = f"[INFRA DeepSecurity_Event] {param_dict['Host']} {Event_Type} Critical Event!"
        description = {'Hostname': param_dict['Host'], 'EventType': '%s' % Event_Type, 'SourceIP': '%s' % SourceIP, 'SourcePort': '%s' % SourcePort, 'DestinationIP': '%s' % DestinationIP, 'DestinationPort': '%s' % DestinationPort, 'Action': '%s' % Action, 'Time': param_dict['TimeStamp']}
        return self._build_json_data(title, description, param_dict['ITSMCaller'])

    def _build_json_data(self, title, description, caller):
        return json.dumps({'operation': 'core/create', 'class': 'Incident', 'fields': {'title': title, 'description': json.dumps(description)}, 'caller': caller, 'comment': 'Create by Elastalert', 'output_fields': 'id, ref, title, description'})

class DeepSecurity_AgentStatus(AlertStrategy):

    def construct_json(self, param_dict):
        Event_Type = 'Agent Status Warning'
        AgentStatus = param_dict['Param1']
        AgentStatusMessages = param_dict['Param2']
        title = f"[INFRA DeepSecurity_Agent] {param_dict['Host']} {Event_Type} Critical Event!"
        description = {'Hostname': param_dict['Host'], 'Agent_status': '%s' % AgentStatus, 'AgentStatusMessages': '%s' % AgentStatusMessages, 'Time': param_dict['TimeStamp']}
        return self._build_json_data(title, description, param_dict['ITSMCaller'])

    def _build_json_data(self, title, description, caller):
        return json.dumps({'operation': 'core/create', 'class': 'Incident', 'fields': {'title': title, 'description': json.dumps(description)}, 'caller': caller, 'comment': 'Create by Elastalert', 'output_fields': 'id, ref, title, description'})

class Elastic_Agent_Status(AlertStrategy):

    def construct_json(self, param_dict):
        status = param_dict['Param1']
        title = f"[INFRA Elastic_Agent] {param_dict['Host']} Status : {status} Event!"
        description = {'Hostname': param_dict['Host'], 'agent_status': status, 'Time': param_dict['TimeStamp']}
        return self._build_json_data(title, description, param_dict['ITSMCaller'])

    def _build_json_data(self, title, description, caller):
        return json.dumps({'operation': 'core/create', 'class': 'Incident', 'fields': {'title': title, 'description': json.dumps(description)}, 'caller': caller, 'comment': 'Create by Elastalert', 'output_fields': 'id, ref, title, description'})

class NMS_GeneralAlert(AlertStrategy):

    def construct_json(self, param_dict):
        Hostname = param_dict['Host']
        rule_name = param_dict['Param1']
        severity = param_dict['Param2']
        title = f'[Network Device] {Hostname} {rule_name} {severity} Event!'
        description = {'Hostname': Hostname, 'device_ip': param_dict['Param3'], 'location': param_dict['Param4'], 'message': param_dict['Param5'], 'alert_time': param_dict['TimeStamp']}
        return self._build_json_data(title, description, param_dict['ITSMCaller'])

    def _build_json_data(self, title, description, caller):
        return json.dumps({'operation': 'core/create', 'class': 'Incident', 'fields': {'title': title, 'description': json.dumps(description)}, 'caller': caller, 'comment': 'Create by Elastalert', 'output_fields': 'id, ref, title, description'})

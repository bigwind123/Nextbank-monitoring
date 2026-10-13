use JSON::Parse 'parse_json';
use POSIX qw(strftime);
use Time::Local;
@All_EventType = qw /antimalware/;

sub Agent_Status {
    $secret_key = '__CFG_0017__';
    $ELK_key = '__CFG_0018__';
    $ELK_key_Header = "-H \"Authorization: ApiKey $ELK_key \" ";
    $Header = "-H \"api-version: v1\" -H \"Accept: application/json\" -H \"api-secret-key: $secret_key\"";
    $Total_Host = `curl -k -X GET __CFG_1524__  $Header \| jq \'.computers\[\].computerStatus\'  \|grep agentStatus\\\" \|wc -l`;
    chomp ($Total_Host);
    system ("curl -k -X GET __CFG_1524__  $Header  > tmp.txt");
    $ELK_Date_Format = strftime ("%Y-%m-%d\T%H:%M:%S\Z", localtime($UnixTime) );
    $ELK_Date_Format = "$ELK_Date_Format";
    my @hostname_list = `cat  tmp.txt  | jq '.computers[].hostName'`;
    system ("cat  tmp.txt  | jq '[.computers[].computerStatus]'  > tmp2.txt");
    for (0..$Total_Host-1){
        $UnixTime = time;
        $UnixTime = $UnixTime - 28800 ;# UTC
        $timestamp = localtime($UnixTime);
        my $ES_host = '__CFG_1522__';
        $ELK_Date_Format = strftime ("%Y-%m-%d\T%H:%M:%S\Z", localtime($UnixTime) );
        $ELK_Date_Format = "$ELK_Date_Format";
        chomp ($current_Agent_Status);
        my $hostname = @hostname_list[$_];
        chomp ($hostname);
        $Seed = int (rand(99999999999));
        $JSON_HeartBeat_ForKibana = `cat  tmp2.txt  \| jq \'.\[$_\]\' | jq \'. \+\= \{\"hostName\":$hostname\,\"timestamp\":\"$ELK_Date_Format\"\}\'\n`;
        $JSON_HeartBeat_ForAlert = `cat  tmp2.txt  \| jq \'.\[$_\]\' | jq \'. \+\= \{\"hostName\":$hostname\,\"\@timestamp\":\"$ELK_Date_Format\"\}\'\n`;
        system ("curl -k -X PUT \"http://$ES_host/ds_health_index/_doc/StatID_$Seed\" $ELK_key_Header -H \"api-version: v1\"  -H \'Content-Type: application/json\' -d \' $JSON_HeartBeat_ForKibana \' ");
        system ("curl -k -X PUT \"http://$ES_host/ds_health_alert/_doc/StatID_$Seed\" $ELK_key_Header -H \"api-version: v1\"  -H \'Content-Type: application/json\' -d \' $JSON_HeartBeat_ForAlert \' ");

    }
}

sub main_Antimalware {
$Catch_Data_Raw = $_;
$EventType = $Catch_Data_Raw;
$ELK_key = '__CFG_0019__';
$ELK_key_Header = "-H \"Authorization: ApiKey $ELK_key \" ";
$DS_ServerIP = '__CFG_1523__';
$DS_ServerPort = '4119';
$GetLoginSession = "curl -k -X POST https://$DS_ServerIP:$DS_ServerPort/rest/authentication/login -H \"Content-Type: application/json\" -H \'api-version: v1\' -H \"Accept: application/json\" -d \'\{\"dsCredentials\": \{\"userName\": \"$UserName\",\"password\": \"$Password\"\}\}\'";
$SessionID = `$GetLoginSession`;
chomp ($SessionID);
print "$SessionID\n";
$GetTime = `date +%s`;
$GetFrequency_min = int (1);
$GetFrequency_min = $GetFrequency_min * 60;
$GetTime_Stamp = ($GetTime - $GetFrequency_min) * 1000;
$GetEvent_Raw_Total = `curl -k -X GET https://$DS_ServerIP:$DS_ServerPort/rest/events/$EventType\\?eventTime=$GetTime_Stamp\\&eventTimeOp=gt\\&sID=$SessionID  -H \"api-version: v1\" -H \"Accept: application/json\" \| jq \'.antiMalwareEventListing.events\[\]\'\|grep logTime\| wc -l`;
print "curl -k -X GET https://$DS_ServerIP:$DS_ServerPort/rest/events/$EventType\\?eventTime=$GetTime_Stamp\\&eventTimeOp=gt\\&sID=$SessionID  -H \"api-version: v1\" -H \"Accept: application/json\" \| jq \'.antiMalwareEventListing.events\[\]\'\|grep logTime\| wc -l\n";
chomp ($GetEvent_Raw_Total);
$GetEvent_Raw = "curl -k -X GET https://$DS_ServerIP:$DS_ServerPort/rest/events/$EventType\\?eventTime=$GetTime_Stamp\\&eventTimeOp=gt\\&sID=$SessionID  -H \"api-version: v1\" -H \"Accept: application/json\" \| jq \'.antiMalwareEventListing.events\[0\]\'";
for (0..$GetEvent_Raw_Total-1){
    my $LogTime =  `curl -k -X GET https://$DS_ServerIP:$DS_ServerPort/rest/events/$EventType\\?eventTime=$GetTime_Stamp\\&eventTimeOp=gt\\&sID=$SessionID  -H \"api-version: v1\" -H \"Accept: application/json\" \| jq \'.antiMalwareEventListing.events\[$_\].logTime\'`;
    chomp ($LogTime);
    print "$LogTime\n";
    $LogTime = $LogTime / 1000;
    $LogDate = gmtime ($LogTime);
    chomp ($LogDate);
    print "$LogDate\n";
    @LogTime_Block_all = split (' ',$LogDate);

    @LogTime_Block_time = split (':',$LogTime_Block_all[3]);
    $ELK_DATE = timelocal ($LogTime_Block_time[2],$LogTime_Block_time[1],$LogTime_Block_time[0],$LogTime_Block_all[2],$LogTime_Block_all[1],"$LogTime_Block_all[4]");
    $ELK_Date_Format = strftime ("%Y-%m-%dT%H:%M:%SZ", localtime ($ELK_DATE));
    $ELK_Date_Format = "$ELK_Date_Format";
    my $JSON = `curl -k -X GET https://$DS_ServerIP:$DS_ServerPort/rest/events/$EventType\\?eventTime=$GetTime_Stamp\\&eventTimeOp=gt\\&sID=$SessionID  -H \"api-version: v1\" -H \"Accept: application/json\" \| jq \'.antiMalwareEventListing.events\[$_\]\'` ;
    $JSON =~ s/(\")(logTime)(\"\:\s+)\d+(.+)/$1\@timestam$3\"$ELK_Date_Format\"$4/;
    system ("curl -k -X PUT \"__CFG_1525__$LogTime\" $ELK_key_Header  -H \'Content-Type: application/json\' -d \' $JSON \' ");
    print "curl -k -X PUT \"__CFG_1525__$LogTime\" $ELK_key_Header  -H \'Content-Type: application/json\' -d \' $JSON \' \n";
    }
    & LogOut();
}


sub LogOut {
    my $SessionID = @_[0];
    $LogOut = "curl -k -X DELETE https://$DS_ServerIP:$DS_ServerPort/rest/authentication/logout?sID=$SessionID  -H \'api-version: v1\' -H \"Accept: application/json\"  ";
    `$LogOut`;
    print "Successed logout by sID: $SessionID\n ";
}


foreach (@All_EventType){
}
& Agent_Status ();

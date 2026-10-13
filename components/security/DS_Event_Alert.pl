#!/usr/bin/perl
use strict;
use DBI;
use JSON::Create 'create_json';
use POSIX qw(strftime);
use Time::Local;
my @EventList;
my $ELK_key = '__CFG_0018__';
my $ELK_key_Header = "-H \"Authorization: ApiKey $ELK_key \" ";
my $ES_URL = '__CFG_0177__';
my $Header = "-H \"api-version: v1\" -H \"Content-Type: application/json\" ";
my $Malware_Json;
my %JSON_Hash;
my @Malware_Json;
my @Malware_Json_1;
my @Malware_Json_2;
my @EventType = qw /antimalwareevents integrityevents intrunsionpreventtionevents/;
my $count ;



foreach (@EventType){
    @Malware_Json =qw//;
    @EventList = qw//;
    & GetEvent ("$_");

    if ($_ =~ /antimalwareevents/ && $#EventList > -1){
        push @EventList,"$_";
        & AntiMalware_Event2Json (@EventList);
        if ($#Malware_Json >= 0){
            foreach (@Malware_Json){
                my $Seed = int (rand(99999999999));
                & Send2ES ($_,$Seed);
            }
        }
    }
    elsif ($_ =~ /integrityevents/ && $#EventList > -1){
        push @EventList,"$_";
        & AntiMalware_Event2Json (@EventList);
        if ($#Malware_Json >= 0){
            foreach (@Malware_Json){
                my $Seed = int (rand(99999999999));
                & Send2ES ($_,$Seed);
            }
        }
    }
    elsif ($_ =~ /intrunsionpreventtionevents/ && $#EventList > -1){
        push @EventList,"$_";
        & AntiMalware_Event2Json (@EventList);
        if ($#Malware_Json >= 0){
            foreach (@Malware_Json){
                my $Seed = int (rand(99999999999));
                & Send2ES ($_,$Seed);
            }
        }
    }
}
sub AntiMalware_Event2Json{
    my $UnixTime = time;
    $UnixTime = $UnixTime - 28800 ;# UTC
    my $timestamp = localtime($UnixTime);
    my $ELK_Date_Format = strftime ("%Y-%m-%d\T%H:%M:%S\Z", localtime($UnixTime) );
    my $ELK_Date_Format = "$ELK_Date_Format";
    my @EventList = @_;
    my @EventList_tmp ;
    for(0..$#EventList-1){
        push (@EventList_tmp,$EventList[$_]);
    }



    my @EventList = @EventList_tmp;
    my $EventList_Count = "$#EventList";

    my $EventType = $_[-1];
    @Malware_Json = qw//;
    foreach (@EventList){
        my @Block = split (/\s+/,$_);
        my $tmp;
        if ($EventType =~ /antimalwareevents/){
            %JSON_Hash = (
            '@timestamp' => "$ELK_Date_Format",
            'EventType' => 'AntiMalware',
            'AntiMalwareEventID' => "$Block[0]",
            'Date' => "$Block[1]$Block[2]",
            'hostname' => "$Block[3]",
            'MalwareName' => "$Block[4]"
            );
        }
        elsif ($EventType =~ /integrityevents/){
            if ($#Block eq 5){
                %JSON_Hash = (
                '@timestamp' => "$ELK_Date_Format",
                'EventType' => 'integrityevents',
                'Date' => "$Block[0]$Block[1]",
                'hostname' => "$Block[2]",
                'IntegrityType' => "$Block[3]",
                'IntegrityPath' => "$Block[4]",
                'Tools' => "$Block[5]"
                );
            }
            if ($#Block eq 7){
                %JSON_Hash = (
                '@timestamp' => "$ELK_Date_Format",
                'EventType' => 'integrityevents',
                'Date' => "$Block[0]$Block[1]",
                'hostname' => "$Block[2]",
                'IntegrityType' => "$Block[3]",
                'IntegrityPath' => "$Block[4]$Block[5]$Block[6]",
                'Tools' => "$Block[7]"
                );
            }

        }
        elsif ($EventType =~ /intrunsionpreventtionevents/){
            my $IPS_ActuinCode = '2';
            if ($Block[8] != 2){
                $Block[8] = 'Detect_Only';
                %JSON_Hash = (
                '@timestamp' => "$ELK_Date_Format",
                'EventType' => "$Block[0]",
                'Date' => "$Block[1]$Block[2]",
                'hostname' => "$Block[3]",
                'SourceIP' => "$Block[4]",
                'SourcePort' => "$Block[5]",
                'DestinationIP' => "$Block[6]",
                'DestinationPort' => "$Block[7]",
                'Action' => "$Block[8]"
                );
            }
            else{
                $Block[8] = 'Reset';
                %JSON_Hash = (
                '@timestamp' => "$ELK_Date_Format",
                'EventType' => "$Block[0]",
                'Date' => "$Block[1]$Block[2]",
                'hostname' => "$Block[3]",
                'SourceIP' => "$Block[4]",
                'SourcePort' => "$Block[5]",
                'DestinationIP' => "$Block[6]",
                'DestinationPort' => "$Block[7]",
                'Action' => "$Block[8]"
                );
            }
        }
        my $Malware_Json = create_json(\%JSON_Hash);
        @Malware_Json_1 = split ('', "$Malware_Json");
        foreach (@Malware_Json_1){
            if ($_ !~ /\}/){
                push @Malware_Json_2, "$_";
            }
            elsif ($_ =~ /\}/){
                my $Result = join ("",@Malware_Json_2);
                $Result = "$Result"."\}";
                @Malware_Json_2 = qw//;
                push @Malware_Json,"$Result";
            }
        }
    }
    return @Malware_Json;
}




sub Send2ES {
    my $tmp_path = '__CFG_1526__';
    my $Malware_Json = $_[0];
    my $Seed = $_[1];
    system ("echo $Malware_Json > $tmp_path");
    print "__CFG_1530__ -k -X PUT \"$ES_URL/ds_event_testing/_doc/Testing_$Seed\" $ELK_key_Header $Header -d  \@$tmp_path \n";
    system ("__CFG_1530__ -k -X PUT \"$ES_URL/ds_event/_doc/Events_$Seed\" $ELK_key_Header $Header -d  \@$tmp_path");
}




sub GetEvent {
    my $Table_Name = $_[0];
    my $sql;
    my $dsn = '__CFG_1527__';
    my $host = '__CFG_1531__,1433';
    my $database = '__CFG_1528__';
    my $user = '__CFG_1529__';
    my $auth = '__CFG_0016__';
    my $Watch_Cycle = 'where LogDate > DATEADD(minute,-15,getdate())';
    @EventList = qw//;
    my $dbh = DBI->connect("$dsn;server=$host;Database=$database",
        $user,
        $auth,
        {RaiseError => 1, AutoCommit => 1}
    ) or die "connect fail\n";
    if ($Table_Name =~ /antimalwareevents/){
        $sql = "select  [AntiMalwareEventID], [LogDate], b.[Hostname],[MalwareName]  FROM dbo.[$Table_Name] a join [hosts] b on a.hostid=b.hostid $Watch_Cycle";
    }
    elsif ($Table_Name =~ /integrityevents/){
        $sql = "select [LogDate], b.[Hostname],[Type],[Keyy],[Process]  FROM dbo.[$Table_Name] a join [hosts] b on a.hostid=b.hostid  $Watch_Cycle";
    }
    elsif ($Table_Name =~ /intrunsionpreventtionevents/){
        $Table_Name = 'payloadlogs';
        $sql = "SELECT 'Intrusion_Prevention' as 'Event Type',LOGDATE,b.HOSTNAME ,SourceIP, SourcePort, DestinationIP, DestinationPort, action from dbo.$Table_Name a join  dsm.dbo.hosts b on a.HostID = b.HostID  $Watch_Cycle";
    }
    my $sth = $dbh->prepare($sql);
    $sth->execute();
    while (my @row = $sth->fetchrow_array()) {
       my ($AntiMalwareEventID, $Date, $hostname, $MalwareName, $block, $block2, $block3, $block4, $block5) = @row;
       push @EventList, ("$AntiMalwareEventID $Date $hostname $MalwareName $block, $block2, $block3, $block4, $block5");
       foreach (@EventList){$_ =~ s/,//g;}
    }
    return @EventList;

}

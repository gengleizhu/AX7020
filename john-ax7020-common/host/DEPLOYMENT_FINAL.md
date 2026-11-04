# 两节点部署及自动授时

每块板使用独立SD卡、节点ID、IP、SSH主机密钥、管理密钥。不要把第一块SD的john-ssh目录或john-management.key复制到第二块。

第一块已验证地址：169.254.173.138/16，ID ax7020-1。
第二块建议地址：169.254.173.139/16，ID ax7020-2；实际地址需现场确认无冲突。
电脑直连地址：169.254.173.137/16。

第二块SD根目录john-node.conf示例：

```sh
NODE_ID=ax7020-2
NODE_IP=169.254.173.139/16
NODE_INTERFACE=eth0
```

两块板均使用相同image.ub/BOOT.BIN（仅适用于已核对一致的AX7020板型），首次启动后分别设置SSH授权及管理密钥。各板在SD的john-ssh目录保存自身dropbear_rsa_host_key及authorized_keys。数据端口42000，管理端口42001。

## 自动授时入口

直连板没有互联网路由，SDK支持连接前从Windows/Linux上位机通过验证主机身份的SSH校时：

```python
with JohnFpgaClient(
    board_ip,
    management_key='credentials/node1-management.key',
    time_sync_ssh={
        'identity_file': 'credentials/node1-login-key',
        'known_hosts_file': 'credentials/known_hosts',
    },
) as client:
    print(client.health())
```

需要系统OpenSSH，SSH私钥通过ssh-agent或部署环境SSH_ASKPASS解锁。首次核对主机指纹后才允许连接。授时失败会抛出异常，不绕过管理请求的60秒时间窗。
这是软件连接节点时自动授时，不是板卡离线上电即拥有准确时间，也不是持续NTP校准。每次重连或重启后重新创建客户端即可重新授时。

## 物理断电验收

记录上电前uptime；确认任务队列空闲并执行sync；断电约10秒再上电。检查主机密钥不变、SSH免密登录、双服务自启、SDK自动授时、默认MD5和远程切换计算。软件reboot不替代此验收。

截至本次更新：第一块软件重启已验证，自动SSH授时入口已实测；物理断电待用户操作，第二块板型/地址/连接待确认。旧PDF为此前接口说明，新增授时与部署以本文件为准。

location ~ ^/socket.io {
    limit_req zone=socketlimit burst=12 nodelay;
    limit_conn socketperip 9;
    proxy_pass http://api.forkdelta.com;
}

location ~ ^/returnTicker {
     limit_req zone=restlimit burst=3 nodelay;
     proxy_pass http://api.forkdelta.com;
}

sqlite3 -header -csv cpower.db "select * from customer; select * from network_service; select * from vnf; select * from vm; select * from vn_group;" > export.csv
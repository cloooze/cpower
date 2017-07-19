BEGIN TRANSACTION;
CREATE TABLE IF NOT EXISTS `VN_GROUP` (
	`VN_GROUP_ID`	INTEGER PRIMARY KEY AUTOINCREMENT,
	`VN_LEFT_ID`	TEXT,
	`VN_LEFT_NAME`	TEXT,
	`VN_LEFT_VIMOBJECT_ID`	TEXT,
	`VN_RIGHT_ID`	TEXT,
	`VN_RIGHT_NAME`	TEXT,
	`VN_RIGHT_VIMOBJECT_ID`	TEXT
);
CREATE TABLE IF NOT EXISTS `VM` (
	`VM_ID`	TEXT NOT NULL,
	`VNF_ID`	TEXT,
	`VM_NAME`	TEXT,
	PRIMARY KEY(`VM_ID`),
	FOREIGN KEY(`VNF_ID`) REFERENCES VNF(`VNF_ID`) ON DELETE CASCADE
);
CREATE TABLE IF NOT EXISTS `VMVNIC` (
	`VM_VNIC_ID`	TEXT,
	`VM_ID`	TEXT,
	`VM_VNIC_NAME`	TEXT,
	`VM_VNIC_IP`	TEXT,
	`VM_VNIC_VIMOBJECT_ID`	TEXT,
	PRIMARY KEY(`VM_VNIC_ID`),
	FOREIGN KEY(`VM_ID`) REFERENCES VM(`VM_ID`) ON DELETE CASCADE
);
CREATE TABLE IF NOT EXISTS `VNF` (
	`VNF_ID`	TEXT NOT NULL,
	`NTW_SERVICE_ID`	TEXT NOT NULL,
	`VN_GROUP_ID`	TEXT NOT NULL,
	`VNF_TYPE`	TEXT NOT NULL,
	`VNF_POSITION`	INTEGER,
	`NTW_SERVICE_BINDING`	TEXT,
	PRIMARY KEY(`VNF_ID`),
	FOREIGN KEY(`NTW_SERVICE_ID`) REFERENCES `NETWORK_SERVICE`(`NTW_SERVICE_ID`),
	FOREIGN KEY(`VN_GROUP_ID`) REFERENCES `VN_GROUP`(`VN_GROUP_ID`)
);
CREATE TABLE IF NOT EXISTS `NETWORK_SERVICE` (
	`NTW_SERVICE_ID`	TEXT NOT NULL,
	`CUSTOMER_ID`	TEXT NOT NULL,
	`NTW_SERVICE_NAME`	TEXT,
	`RT_LEFT`	TEXT NOT NULL,
	`RT_RIGHT`	TEXT NOT NULL,
	`RT_MGMT`	TEXT,
	`NTW_POLICY`	TEXT,
	`VLINK_NAME`	TEXT,
	`VLINK_ID`	TEXT,
	PRIMARY KEY(`NTW_SERVICE_ID`),
	FOREIGN KEY(`CUSTOMER_ID`) REFERENCES CUSTOMER(`CUSTOMER_ID`)
);
CREATE TABLE IF NOT EXISTS `CUSTOMER` (
	`CUSTOMER_ID`	TEXT NOT NULL,
	`CUSTOMER_NAME`	TEXT,
	PRIMARY KEY(`CUSTOMER_ID`)
);
COMMIT;

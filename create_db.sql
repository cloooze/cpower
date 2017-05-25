BEGIN TRANSACTION;
CREATE TABLE IF NOT EXISTS `VN_GROUP` (
	`VN_GROUP_ID`	INTEGER PRIMARY KEY AUTOINCREMENT,
	`VNF_ID`	TEXT,
	`VN_LEFT_ID`	TEXT,
	`VN_LEFT_NAME`	TEXT,
	`VN_RIGHT_ID`	TEXT,
	`VN_RIGHT_NAME`	TEXT,
	FOREIGN KEY(`VNF_ID`) REFERENCES VNF(`VNF_ID`) ON DELETE CASCADE
);
CREATE TABLE IF NOT EXISTS `VM` (
	`VM_ID`	TEXT NOT NULL,
	`VNF_ID`	TEXT,
	`VM_VNIC1_ID`	TEXT,
	`VM_VNIC1_ID_NAME`	TEXT,
	`VM_VNIC1_VIMOBJECT_ID`	TEXT,
	`VM_VNIC2_ID`	TEXT,
	`VM_VNIC2_ID_NAME`	TEXT,
	`VM_VNIC2_VIMOBJECT_ID`	TEXT,
	PRIMARY KEY(`VM_ID`),
	FOREIGN KEY(`VNF_ID`) REFERENCES VNF(`VNF_ID`) ON DELETE CASCADE
);
CREATE TABLE IF NOT EXISTS `VNF` (
	`VNF_ID`	TEXT NOT NULL,
	`NTW_SERVICE_ID`	TEXT NOT NULL,
	`NTW_POLICY`	TEXT,
	`VNF_POSITION`	TEXT,
	`NTW_SERVICE_BINDING`	TEXT,
	PRIMARY KEY(`VNF_ID`),
	FOREIGN KEY(`NTW_SERVICE_ID`) REFERENCES `NETWORK_SERVICE`(`NTW_SERVICE_ID`) ON DELETE CASCADE
);
CREATE TABLE IF NOT EXISTS `NETWORK_SERVICE` (
	`NTW_SERVICE_ID`	TEXT NOT NULL,
	`CUSTOMER_ID`	TEXT NOT NULL,
	`NTW_SERVICE_NAME`	TEXT,
	`RT_LEFT`	TEXT NOT NULL,
	`RT_RIGHT`	TEXT NOT NULL,
	`RT_MGMT`	TEXT NOT NULL,
	`VNF_TYPE`	TEXT NOT NULL,
	`NTW_POLICY`	TEXT,
	`VLINK_NAME`	TEXT,
	`VLINK_UUID`	TEXT,
	PRIMARY KEY(`NTW_SERVICE_ID`),
	FOREIGN KEY(`CUSTOMER_ID`) REFERENCES CUSTOMER(`CUSTOMER_ID`)
);
CREATE TABLE IF NOT EXISTS `CUSTOMER` (
	`CUSTOMER_ID`	TEXT NOT NULL,
	`CUSTOMER_NAME`	TEXT,
	PRIMARY KEY(`CUSTOMER_ID`)
);
CREATE TABLE IF NOT EXISTS `ORDER` (
	`ORDER_ID`	TEXT NOT NULL,
	`ORDER_TYPE`	TEXT NOT NULL,
	`STATUS`	TEXT,
	PRIMARY KEY(`ORDER_ID`)
);
COMMIT;

# Dictionary overview

![Dictionary overview](https://github.com/sb-ncbr/tunnels-schema/blob/main/images/schema.png)

See the [full version](https://github.com/sb-ncbr/tunnels-schema/blob/main/images/schema_full.png) with the descriptions.

# Updating dictionary

After updating the dictionary, check whether the file is valid:

```bash
gemmi validate -v mmcif_tunnels_v10.dic
```

# Information to set in mmCIF
```
loop_
_audit_conform.dict_name
_audit_conform.dict_version
_audit_conform.dict_location
mmcif_tunnels_v10.dic       1.0      https://sb-ncbr.github.io/tunnels-schema/schemas/mmcif_tunnels_v10.dic
```

# Checking the mmCIF

```bash
gemmi validate -v -d mmcif_tunnels_v10.dic structure.cif
```

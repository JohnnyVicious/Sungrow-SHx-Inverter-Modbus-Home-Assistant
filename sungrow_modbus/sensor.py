import logging
from homeassistant.helpers.entity import Entity
from homeassistant.components.sensor import SensorEntity
from datetime import timedelta
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator
from .model_registry import ModelRegistry, Register
from pymodbus.client import ModbusTcpClient

_LOGGER = logging.getLogger(__name__)

async def async_setup_entry(hass, entry, async_add_entities):
    """Set up Sungrow Modbus sensors from config entry."""
    host = entry.data["host"]
    port = entry.data["port"]
    slave = entry.data["slave"]
    name = entry.data["name"]
    
    # Create modbus client
    client = ModbusTcpClient(host=host, port=port)
    client.connect()
    
    # Create coordinator
    coordinator = SungrowModbusCoordinator(hass, client, slave)
    await coordinator.async_config_entry_first_refresh()
    
    # Get device model
    model_code = coordinator.data.get("device_type_code")
    if not model_code:
        _LOGGER.error("Failed to get device type code")
        return False
    
    # Get register map
    model_registry = ModelRegistry()
    registers = model_registry.get_model(model_code)
    if not registers:
        _LOGGER.error(f"Unsupported model: {hex(model_code)}")
        return False
    
    # Create entities
    entities = []
    for reg in registers:
        entities.append(SungrowModbusSensor(
            coordinator, 
            reg, 
            name,
            slave
        ))
    
    async_add_entities(entities)

class SungrowModbusCoordinator(DataUpdateCoordinator):
    """Data update coordinator for Sungrow Modbus."""
    
    def __init__(self, hass, client, slave):
        """Initialize."""
        super().__init__(
            hass,
            _LOGGER,
            name="Sungrow Modbus",
            update_interval=timedelta(seconds=10)
        )
        self.client = client
        self.slave = slave
        self.data = {}
    
    async def _async_update_data(self):
        """Fetch all register data."""
        data = {}
        # Read device type code first to confirm model
        device_type_result = await self.hass.async_add_executor_job(
            self.client.read_holding_registers,
            4999,  # register 5000
            1,
            self.slave
        )
        
        if device_type_result.isError():
            _LOGGER.error("Error reading device type code: %s", device_type_result)
            return {}
        
        model_code = device_type_result.registers[0]
        data["device_type_code"] = model_code
        
        # Get register map for this model
        model_registry = ModelRegistry()
        registers = model_registry.get_model(model_code)
        if not registers:
            _LOGGER.error("Unsupported model: %s", hex(model_code))
            return {}
        
        # Batch read registers in contiguous groups
        registers.sort(key=lambda r: r.address)
        current_group = []
        
        for reg in registers:
            if not current_group:
                current_group.append(reg)
                continue
                
            last_reg = current_group[-1]
            # Check if contiguous
            if reg.address == last_reg.address + last_reg.count:
                current_group.append(reg)
            else:
                # Read current group
                await self._read_register_group(current_group, data)
                current_group = [reg]
        
        # Read remaining group
        if current_group:
            await self._read_register_group(current_group, data)
        
        return data

    def _read_register_group(self, registers, data):
        """Read a contiguous group of registers."""
        start_address = registers[0].address
        count = sum(reg.count for reg in registers)
        
        # Determine register type (input or holding)
        reg_type = registers[0].register_type
        if reg_type == "input":
            result = self.client.read_input_registers(start_address, count, slave=self.slave)
        else:
            result = self.client.read_holding_registers(start_address, count, slave=self.slave)
            
        if result.isError():
            _LOGGER.error("Error reading registers %s-%s: %s", 
                          start_address, start_address+count-1, result)
            return
        
        # Process results
        offset = 0
        for reg in registers:
            if reg.data_type == "string":
                # Convert to ASCII string
                chars = []
                for i in range(reg.count):
                    word = result.registers[offset + i]
                    chars.append(chr((word >> 8) & 0xFF))
                    chars.append(chr(word & 0xFF))
                value = ''.join(chars).replace('\x00', '').strip()
                offset += reg.count
            elif reg.data_type == "uint16":
                value = result.registers[offset]
                offset += 1
            elif reg.data_type == "int16":
                value = result.registers[offset]
                if value > 0x7FFF:
                    value = value - 0x10000
                offset += 1
            elif reg.data_type == "uint32":
                value = (result.registers[offset] << 16) | result.registers[offset+1]
                offset += 2
            elif reg.data_type == "int32":
                value = (result.registers[offset] << 16) | result.registers[offset+1]
                if value > 0x7FFFFFFF:
                    value = value - 0x100000000
                offset += 2
            else:
                value = None
                offset += reg.count
            
            data[reg.address] = value

class SungrowModbusSensor(SensorEntity):
    """Representation of a Sungrow Modbus sensor."""
    
    def __init__(self, coordinator, register, device_name, slave):
        """Initialize the sensor."""
        self.coordinator = coordinator
        self.register = register
        self._name = f"{device_name} {register.name}"
        self._unique_id = f"sungrow_{slave}_{register.address}"
        self._device_name = device_name
    
    @property
    def unique_id(self):
        """Return a unique ID."""
        return self._unique_id
    
    @property
    def name(self):
        """Return the name of the sensor."""
        return self._name
    
    @property
    def state(self):
        """Return the state of the sensor."""
        # Get value from coordinator data by register address
        value = self.coordinator.data.get(self.register.address)
        
        # Apply scaling if value exists
        if value is not None and self.register.scale != 1.0:
            return value * self.register.scale
        return value
    
    @property
    def unit_of_measurement(self):
        """Return the unit of measurement."""
        return self.register.unit
    
    @property
    def device_class(self):
        """Return the device class."""
        return self.register.device_class
    
    @property
    def state_class(self):
        """Return the state class."""
        return self.register.state_class
    
    @property
    def device_info(self):
        """Return device information."""
        return {
            "identifiers": {("sungrow_modbus", self._device_name)},
            "name": self._device_name,
            "manufacturer": "Sungrow",
        }

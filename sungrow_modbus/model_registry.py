"""Model registry for Sungrow inverters."""
from dataclasses import dataclass

@dataclass
class Register:
    address: int
    name: str
    data_type: str
    count: int = 1
    scale: float = 1.0
    unit: str = None
    device_class: str = None
    state_class: str = None
    register_type: str = "input"  # "input" or "holding"

class ModelRegistry:
    def __init__(self):
        self.models = {
            0x0E03: self._create_sh10rt,
            0x0E26: self._create_sh25t
        }
    
    def get_model(self, model_code):
        create_func = self.models.get(model_code)
        if create_func:
            return create_func()
        return None
    
    def _create_base_registers(self):
        """Common registers for all models"""
        return [
            Register(4989, "Serial Number", "string", count=10),
            Register(4999, "Device Type Code", "uint16"),
            Register(5007, "Inverter Temperature", "int16", scale=0.1, unit="°C", device_class="temperature"),
            # More common registers...
        ]
    
    def _create_sh10rt(self):
        """SH10RT-V112 model registers"""
        registers = self._create_base_registers()
        registers.extend([
            Register(5010, "MPPT1 Voltage", "uint16", scale=0.1, unit="V", device_class="voltage"),
            Register(5011, "MPPT1 Current", "uint16", scale=0.1, unit="A", device_class="current"),
            Register(5012, "MPPT2 Voltage", "uint16", scale=0.1, unit="V", device_class="voltage"),
            Register(5013, "MPPT2 Current", "uint16", scale=0.1, unit="A", device_class="current"),
            # More SH10RT-specific registers...
        ])
        return registers
    
    def _create_sh25t(self):
        """SH25T-V11 model registers (with additional MPPT3)"""
        registers = self._create_base_registers()
        registers.extend([
            Register(5010, "MPPT1 Voltage", "uint16", scale=0.1, unit="V", device_class="voltage"),
            Register(5011, "MPPT1 Current", "uint16", scale=0.1, unit="A", device_class="current"),
            Register(5012, "MPPT2 Voltage", "uint16", scale=0.1, unit="V", device_class="voltage"),
            Register(5013, "MPPT2 Current", "uint16", scale=0.1, unit="A", device_class="current"),
            Register(5014, "MPPT3 Voltage", "uint16", scale=0.1, unit="V", device_class="voltage"),
            Register(5015, "MPPT3 Current", "uint16", scale=0.1, unit="A", device_class="current"),
            Register(5016, "Total DC Power", "uint32", scale=1, unit="W", device_class="power"),
            # Add more SH25T-specific registers as needed
        ])
        return registers

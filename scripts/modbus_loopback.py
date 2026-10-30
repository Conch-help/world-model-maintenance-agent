import asyncio
import json
from pathlib import Path
from pymodbus.client import AsyncModbusTcpClient
from pymodbus.datastore import ModbusDeviceContext, ModbusServerContext, ModbusSequentialDataBlock
from pymodbus.server import StartAsyncTcpServer
from wm_maint.adapters.plc_contract import PLCCommandFrame, PLCStateFrame, validate_command, modes_to_coils, state_to_registers
from wm_maint.plant import MODE_DERATE, MODE_FULL, MODE_MAINTENANCE


async def main():
    state = PLCStateFrame([0.75, 0.95, 0.97], [30.8, 30.9, 32.8], [0.19, 0.13, 0.14], 56.98, 0.1218)
    registers = [int(round(v * 1000)) & 0xFFFF for v in state_to_registers(state)]
    coils = modes_to_coils([MODE_DERATE, MODE_FULL, MODE_MAINTENANCE])
    device = ModbusDeviceContext(
        co=ModbusSequentialDataBlock(1, [False] * 16),
        hr=ModbusSequentialDataBlock(1, [0] * 32),
    )
    context = ModbusServerContext(devices={1: device}, single=False)
    server = asyncio.create_task(StartAsyncTcpServer(context, address=("127.0.0.1", 5502)))
    await asyncio.sleep(1.0)
    client = AsyncModbusTcpClient("127.0.0.1", port=5502)
    await client.connect()
    for i, value in enumerate(registers[:20]):
        await client.write_register(1 + i, value, device_id=1)
    for i, value in enumerate(coils):
        await client.write_coil(1 + i, value, device_id=1)
    rr = await client.read_holding_registers(1, count=20, device_id=1)
    cr = await client.read_coils(1, count=3, device_id=1)
    command = PLCCommandFrame([MODE_DERATE, MODE_FULL, MODE_MAINTENANCE], "APPROVAL-1", "TRACE-1")
    validation = validate_command(state, command)
    result = {
        "register_values": rr.registers,
        "coils": cr.bits[:3],
        "validation": {"accepted": validation.accepted, "reasons": validation.reasons},
        "protocol": "Modbus TCP loopback",
    }
    out = Path("artifacts/modbus_loopback.json")
    out.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False, indent=2))
    client.close()
    server.cancel()
    try:
        await server
    except asyncio.CancelledError:
        pass


if __name__ == "__main__":
    asyncio.run(main())

#!/usr/bin/env python3

try:
    print("Starting test...")
    from harvest.broker.mock import MockBroker
    print("Import successful")

    broker = MockBroker()
    print("Creation successful")

    print("Exchange:", broker.exchange)
    print("Test completed successfully!")

except Exception as e:
    print("Error occurred:", str(e))
    import traceback
    traceback.print_exc()

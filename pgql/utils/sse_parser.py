# pgql/utils/sse_parser.py

from typing import Dict, Generator, Optional
import logging
import json

logger = logging.getLogger(__name__)


def parse_sse_stream(response) -> Generator[Dict, None, None]:
    """Parse Server-Sent Events (SSE) stream.
    
    Yields dictionaries representing individual SSE events.
    
    Args:
        response: HTTP response object with iter_lines method
    
    Yields:
        Dict containing parsed event data
    """
    event_data = ""
    event_type = None
    event_id = None
    
    for line in response.iter_lines(decode_unicode=True):
        if not line:
            # Empty line = end of event
            if event_data:
                parsed_data = _parse_event_data(event_data)
                if event_type:
                    parsed_data['event'] = event_type
                if event_id:
                    parsed_data['id'] = event_id
                yield parsed_data
                
                # Reset for next event
                event_data = ""
                event_type = None
                event_id = None
            continue
        
        if line.startswith("data: "):
            event_data += line[6:]  # Remove "data: " prefix
        elif line.startswith("event: "):
            event_type = line[7:]  # Remove "event: " prefix
        elif line.startswith("id: "):
            event_id = line[4:]  # Remove "id: " prefix
    
    # Yield final event if exists
    if event_data:
        parsed_data = _parse_event_data(event_data)
        if event_type:
            parsed_data['event'] = event_type
        if event_id:
            parsed_data['id'] = event_id
        yield parsed_data


def _parse_event_data(data: str) -> Dict:
    """Parse event data as JSON.
    
    Args:
        data: Raw event data string
    
    Returns:
        Dict containing parsed data, or empty dict if parsing fails
    """
    try:
        return json.loads(data)
    except json.JSONDecodeError:
        logger.error(f"Failed to parse SSE data: {data}")
        return {"raw_data": data}


def collect_sse_stream(response) -> Dict:
    """Collect and merge all events from SSE stream into single dict.
    
    This is useful for getting final state after all events.
    
    Args:
        response: HTTP response object with iter_lines method
    
    Returns:
        Dict containing merged data from all events
    """
    result = {}
    for event in parse_sse_stream(response):
        result.update(event)
    return result

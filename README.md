# Butter Beer Banter

```python
def send(message):
    try:
        sent = client.send(dumbledore, message)
	if sent:
	    harry.log('contacted D', message)
	    return True
	else:
	    harry.log('check yer wand, Harry', message, client.history['last'])
	    return False
    except WizardError as ex:
	harry.log(ex, 'youre a wizard, Harry')
	return False
```
    

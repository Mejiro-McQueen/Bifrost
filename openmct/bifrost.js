class Bifrost{
	constructor(config){
		this.config = config
		//console.log(this.config)
		this.tlm_dict_promise = this.getDictionary(this.config.bifrost_endpoints.tlm_dictionary)
		//console.log(tlm_dict_promise)
	}
	
	async getDictionary(endpoint) {
		return fetch(endpoint, {method: "GET"}).then(async resp =>{
			const data = await resp.json()
			return data
		})
	}

	Integration(){
		const {config} = this.config
		const tlm_dict_promise = this.tlm_dict_promise
		//console.log(this)

		const rootObjectProvider = {
			// What do display
			get: function (identifier) {
				return tlm_dict_promise.then(dictionary => {
					return {
						identifier,
						name: 'Tuatha_de_Danaan',
						type: 'folder',
						location: 'Tuatha_de_Danaan'
					}
				})
			}
		}

		const subsystemCompositionProvider = {
			// What do display
			appliesTo: function (domainObject) {
				// console.log("\nNyanNyan")
				// console.log(domainObject.identifier)
				// console.log(domainObject.namespace)
				// console.log(domainObject.type)
				const res = domainObject.identifier.namespace === 'bifrost.Tuatha_de_Danaan' &&
					domainObject.type === 'folder';
				//console.log(res, domainObject.identifier.namespace)
				return res
			},
			load: function (domainObject) {
				return tlm_dict_promise.then(dictionary => {
					//console.log(domainObject)
					//const subsystems = ["All Subsystems"] // Get Subsystems Here
					const subsystems = [...new Set(Object.values(dictionary).map(function (d){return d.subsystem}))]
					//console.log(subsystems)
					const res =  subsystems.map(function (subsystem) {
						return {
							namespace: 'bifrost.Tuatha_de_Danaan.Subsystem',
							key: subsystem
						}
					})
					return res
				})
			}
		}
		
		const packetCompositionProvider = {
			// What do display
			appliesTo: function (domainObject) {
				// console.log("\nNyanNyan")
				// console.log(domainObject.identifier)
				// console.log(domainObject.namespace)
				// console.log(domainObject.type)
				const res = domainObject.identifier.namespace === 'bifrost.Tuatha_de_Danaan.Subsystem'// &&
					//domainObject.type === 'folder';
				return res
			},
			load: function (domainObject) {
				return tlm_dict_promise.then(dictionary => {
					//console.log(domainObject.identifier.key)
					const all_fields = Object.keys(dictionary).map(function (m) {
						const res = {
							namespace: 'bifrost.Tuatha_de_Danaan.Telemetry.Packet',
							key: m
						}
						return res 
					})
					const filtered_fields = all_fields.filter(function (current){
						return  dictionary[current.key].subsystem == domainObject.identifier.key
					} )
					//console.log(filtered_fields)
					return filtered_fields
				})
			}
		}

		const fieldCompositionProvider = {
			// What do display
			appliesTo: function (domainObject) {
				// console.log("\nNyanNyan")
				// console.log(domainObject.identifier.name, domainObject.namespace)
				// console.log(domainObject.type)
				return domainObject.identifier.namespace === 'bifrost.Tuatha_de_Danaan.Telemetry.Packet' &&
					domainObject.type === 'bifrost.telemetry.packet';
			},
			load: function (domainObject) {
				return tlm_dict_promise.then(dictionary => {
					//console.log(domainObject.identifier.key)
					return Object.keys(dictionary[domainObject.identifier.key].fields).map(function (m) {
						const res = {
							namespace: 'bifrost.Tuatha_de_Danaan.Telemetry.Packet.Field',
							key: `${domainObject.identifier.key}.${m}`
						}
						//console.log(res)
						return res
					})
				})
			}
		}

		const packetMetadataProvider = {
			// How to display
			get: function (identifier) {
				let key = identifier.key
				//console.log(identifier.namespace, identifier.key)
				return tlm_dict_promise.then(dictionary => {
					const res = {
						identifier,
						name: key,
						type: 'bifrost.telemetry.packet',
						location: 'bifrost.Tuatha_de_Danaan' //What does this parameter even do?
					}
					//console.log(res)
					return res 
				})
			}
		}

		const fieldMetadataProvider = {
			// How to display
			get: function (identifier) {
				let key = identifier.key
				let namespace = identifier.namespace
				//console.log(namespace, key)
				return tlm_dict_promise.then(dictionary => {
					const res = {
						identifier: identifier,
						name: key,
						type: 'bifrost.telemetry.packet.field',
						location: 'bifrost.Tuatha_de_Danaan', //What does this parameter even do?
						telemetry: {
							values: [
								{
									key: "RE",
									name: "VALUE",
									//"unit": "kilograms",
									//"format": "native",
									//"min": -10,
									//"max": 10,
									"hints": {
										"range": 1
									}
								},
								{
									key: 'utc',
									source: 'timestamp',
									name: 'Timestamp',
									format: 'utc',
									hints: { domain: 1 },
								}
							]
						}
						
					}
					//console.log(res)
					return res 
				})
			}
		}
		
		const subsystemMetadataProvider = {
			// How to display
			get: function (identifier) {
				let key = identifier.key
				let namespace = identifier.namespace
				//console.log(namespace, key)
				return tlm_dict_promise.then(dictionary => {
					const res = {
						identifier,
						name: key,
						type: 'bifrost.telemetry.subsystem',
						location: 'bifrost.Tuatha_de_Danaan' //What does this parameter even do?
					}
					return res 
				})
			}
		}
		
		return openmct => {
			//console.log(openmct)
			openmct.objects.addRoot({
				namespace: 'bifrost.Tuatha_de_Danaan',
				key: 'spacecraft'
			})
			
			openmct.objects.addProvider('bifrost.Tuatha_de_Danaan', rootObjectProvider)
			openmct.objects.addProvider('bifrost.Tuatha_de_Danaan.Subsystem', subsystemMetadataProvider)
			openmct.composition.addProvider(subsystemCompositionProvider)

			openmct.objects.addProvider('bifrost.Tuatha_de_Danaan.Telemetry.Packet', packetMetadataProvider)
			openmct.composition.addProvider(packetCompositionProvider)
			
			openmct.objects.addProvider('bifrost.Tuatha_de_Danaan.Telemetry.Packet.Field', fieldMetadataProvider)
			openmct.composition.addProvider(fieldCompositionProvider)
			
			openmct.types.addType('bifrost.telemetry.packet', {
				name: 'Packet',
				description: 'Bifrost Packet',
				cssClass: 'icon-packet',
			});

			openmct.types.addType('bifrost.telemetry.packet.field', {
				name: 'Field',
				description: 'Bifrost Field',
				cssClass: 'icon-telemetry',
			});

			openmct.types.addType('bifrost.telemetry.subsystem', {
				name: 'Subsystem',
				description: 'Bifrost Subsystem',
				cssClass: 'icon-notebook',
			});
		}
	}

	RealtimeTelemetry() {
		return function (openmct) {
			const socket = new WebSocket("ws://localhost:8000/telemetry")
			var listener = {};
			
			socket.onmessage = function (event) {
				//console.log("Got message")
				const bifrost_packet = JSON.parse(event.data)
				const decoded_map = bifrost_packet.decoded_packet
				//console.log(decoded_map)
				// Need to unpack field: value?
				const points = Object.entries(decoded_map).map(function (m) {
					//console.log(typeof(m[1]), m[1])
					const datum = {
						id: `${bifrost_packet.packet_name}.${m[0]}`,
						timestamp: `${bifrost_packet.packet_time .split(' ') .join('T') .slice(0, -3)}Z`,
						//value: m[1],
						RE: m[1],
						//status: 1,
					}
					//console.log(datum)
					return datum
				})
				//console.log("NICO NICO NII")
				//console.log(Object.keys(listener))
				
				points.forEach(function (point) {
					//console.log(point.id)
					if (listener[point.id]) {
						//console.log("HIT!")
						listener[point.id](point)
					}
					return 
				})
			}
			
			var telemetryProvider = {
				supportsSubscribe: function (domainObject) { 
					//console.log(domainObject.type)
					return domainObject.type === 'bifrost.telemetry.packet.field'
				},
				
				supportsRequest: function (domainObject, options){
					return false },
				
				subscribe: function (domainObject, callback) {
					listener[domainObject.identifier.key] = callback
					//console.log("NICO NICO")
					//console.log(domainObject.identifier.key)
					//console.log(listener)
					return function unsubscribe() {
						delete listener[domainObject.identifier.key]
					}
				}
			}
			openmct.telemetry.addProvider(telemetryProvider);
		}
	}
}



#!/usr/bin/python

import os
import logging
import pprint
import json
import os.path
import ConfigParser
import random
import time

from datetime import datetime

from pgoapi import PGoApi
from pgoapi import utilities as util

from __init___ import config

log = logging.getLogger(__name__)


def get_pokemon_name(pokemon_id):
    if not hasattr(get_pokemon_name, 'names'):
        file_path = "pokemon.json"
        with open(file_path, 'r') as f:
            get_pokemon_name.names = json.loads(f.read())
    return get_pokemon_name.names[str(pokemon_id)]


def parse_map(map_dict):
    pokemons = {}

    cells = map_dict['responses']['GET_MAP_OBJECTS']['map_cells']
    for cell in cells:
        for p in cell.get('wild_pokemons', []):
            d_t = datetime.utcfromtimestamp(
                (p['last_modified_timestamp_ms'] +
                 p['time_till_hidden_ms']) / 1000.0)

            pokemons[p['encounter_id']] = {
                # 'encounter_id': b64encode(str(p['encounter_id'])),
                'spawnpoint_id': p['spawn_point_id'],
                'pokemon_name': get_pokemon_name(p['pokemon_data']['pokemon_id']),
                'pokemon_id': p['pokemon_data']['pokemon_id'],
                'latitude': p['latitude'],
                'longitude': p['longitude'],
                'disappear_time': d_t,
                'distance': 0
            }
            # pokemon['distance'] = distance.distance(origin, loc).meters

    # print('Pokemon: \n\r{}'.format(pprint.PrettyPrinter(indent=4).pformat(pokemons)))

    #if pokemons:
    #    log.info("Upserting {} pokemon".format(len(pokemons)))

    return pokemons


def generate_spiral(starting_lat, starting_lng, step_size, step_limit):
    coords = [{'lat': starting_lat, 'lng': starting_lng}]
    steps, x, y, d, m = 1, 0, 0, 1, 1
    rlow = 0.0
    rhigh = 0.0005

    while steps < step_limit:
        while 2 * x * d < m and steps < step_limit:
            x = x + d
            steps += 1
            lat = x * step_size + starting_lat + random.uniform(rlow, rhigh)
            lng = y * step_size + starting_lng + random.uniform(rlow, rhigh)
            coords.append({'lat': lat, 'lng': lng})
        while 2 * y * d < m and steps < step_limit:
            y = y + d
            steps += 1
            lat = x * step_size + starting_lat + random.uniform(rlow, rhigh)
            lng = y * step_size + starting_lng + random.uniform(rlow, rhigh)
            coords.append({'lat': lat, 'lng': lng})

        d = -1 * d
        m = m + 1
    return coords


def write_pokemons(pokemons):
    arr = list()
    i = 0
    for key, value in pokemons.items():
        if not value['pokemon_name']:
            continue
        i += 1
        data = {}
        data['id'] = key
        data['name'] = value['pokemon_name']
        data['lat'] = value['latitude']
        data['long'] = value['longitude']
        # data['disappear'] = value['disappear_time'].strftime("%d-%m-%Y %H:%M:%S")
        data['disappear'] = value['disappear_time'].strftime("%H:%M:%S")
        data['idx'] = i

        arr.append(data)

        log.debug("Writing '" + str(data) + "'")

    with open('web/data.json', 'w') as outfile:
        json.dump(arr, outfile)


def find_pokemons(api, position):
    step_size = 0.0015
    step_limit = 49

    coords = generate_spiral(position[0], position[1], step_size, step_limit)

    cell_ids = util.get_cell_ids(position[0], position[1])
    # timestamps = [0, ] * len(cell_ids)
    timestamps = [0, ] * len(cell_ids)

    pokemons = {}

    for coord in coords:
        lat = coord['lat']
        lng = coord['lng']
        api.set_position(lat, lng, 0)

        response_dict = api.get_map_objects(latitude=util.f2i(position[0]),
                            longitude=util.f2i(position[1]),
                            since_timestamp_ms=timestamps,
                            cell_id=cell_ids)
        resp = parse_map(response_dict)

        pokemons.update(resp)
        time.sleep(0.51)

    return pokemons


def main():
    # log settings
    # log format
    logging.basicConfig(level=logging.DEBUG, format='%(asctime)s [%(module)10s] [%(levelname)5s] %(message)s')
    # log level for http request class
    logging.getLogger("requests").setLevel(logging.WARNING)
    # log level for main pgoapi class
    logging.getLogger("pgoapi").setLevel(logging.INFO)
    # log level for internal pgoapi class
    logging.getLogger("rpc_api").setLevel(logging.INFO)

    locations = config['LOCATIONS'].split(";")

    pokemons = {}

    for location in locations:
        api = PGoApi()

        position = util.get_pos_by_name(location)
        if not position:
            log.error('Your given location could not be found by name')
            return

        if not api.login(config['SERVICE'], config['USERNAME'], config['PASSWORD'], position[0], position[1], 0, True):
            return

        poke = {}
        poke = find_pokemons(api, position)
        if poke:
            pokemons.update(poke)
            write_pokemons(pokemons)

        if len(locations) > 1:
            time.sleep(0.51)


def replace_web():
    with open('web/index.html_template') as infile, open('web/index.html', 'w') as outfile:
        for line in infile:
            line = line.replace('GMAPS_API_KEY', config['GMAPS_API'])
            outfile.write(line)


def parse_config():
    Config = ConfigParser.ConfigParser()
    filename = 'config.ini'
    if os.path.isfile('config.ini_dev'):
        filename = 'config.ini_dev'
    Config.read(os.path.join(os.path.dirname(__file__), filename))
    config['SERVICE'] = Config.get('Authentication', 'service')
    config['USERNAME'] = Config.get('Authentication', 'username')
    config['PASSWORD'] = Config.get('Authentication', 'password')
    config['LOCATIONS'] = Config.get('Location', 'locations')
    config['GMAPS_API'] = Config.get('Apis', 'google_maps')


if __name__ == '__main__':
    parse_config()
    replace_web()
    main()

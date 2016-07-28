import os
import logging
import pprint
import json
import os.path
import ConfigParser

from datetime import datetime

from pgoapi import PGoApi
from pgoapi import utilities as util

from __init___ import config

log = logging.getLogger(__name__)

TIMESTAMP = '\000\000\000\000\000\000\000\000\000\000\000\000\000\000\000\000\000\000\000\000\000'

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
                'disappear_time': d_t
            }

    print('Pokemon: \n\r{}'.format(pprint.PrettyPrinter(indent=4).pformat(pokemons)))

    if pokemons:
        log.info("Upserting {} pokemon".format(len(pokemons)))

    return pokemons


def write_pokemons(pokemons):
    data_arr = []
    data = {}
    i = 1
    for key, value in pokemons.items():
        i += 1
        data['id'] = key
        data['name'] = value['pokemon_name']
        data['lat'] = value['latitude']
        data['long'] = value['longitude']
        data['idx'] = i

        print('Pokemon: \n\r{}'.format(pprint.PrettyPrinter(indent=4).pformat(data)))

        data_arr.append(data)

    with open('web/data.json', 'w') as outfile:
        json.dump(data_arr, outfile)


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

    api = PGoApi()

    if not api.login(config['SERVICE'], config['USERNAME'], config['PASSWORD']):
        return

    position = util.get_pos_by_name(config['LOCATIONS'])
    if not position:
        log.error('Your given location could not be found by name')
        return

    cell_ids = util.get_cell_ids(position[0], position[1])
    timestamps = [0, ] * len(cell_ids)

    api.set_position(*position)
    api.get_map_objects(latitude=util.f2i(position[0]),
                        longitude=util.f2i(position[1]),
                        since_timestamp_ms=timestamps,
                        cell_id=cell_ids)
    response_dict = api.call()

    pokemons = {}
    pokemons = parse_map(response_dict)

    if not pokemons:
        log.error('Cannot found pokemons')
        return

    write_pokemons(pokemons)


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

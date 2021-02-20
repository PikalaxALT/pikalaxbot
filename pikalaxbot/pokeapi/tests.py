from pikalaxbot.paths import __dirname__
from pikalaxbot.pokeapi.database import *
from pikalaxbot.pokeapi.models import *
import unittest


class PokeAPITests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self) -> None:
        self.conn = await connect(
            f'file:{__dirname__}/../pokeapi/db.sqlite3?mode=ro',
            uri=True,
            check_same_thread=False
        )

    def testAssertPrepared(self):
        self.assertTrue(PokeapiModel.__prepared__)

    async def testGetMonMatchupAgainstType(self):
        mon = await PokeapiModel.classes.PokemonSpecies.get(self.conn, 25)
        type_ = await PokeapiModel.classes.Type.get(self.conn, 3)
        self.assertEqual(await self.conn.get_mon_matchup_against_type(mon, type_), 0.5)

    async def testGetMonMatchupAgainstMove(self):
        mon = await PokeapiModel.classes.PokemonSpecies.get(self.conn, 19)
        move = await PokeapiModel.classes.Move.get(self.conn, 560)
        self.assertEqual(await self.conn.get_mon_matchup_against_move(mon, move), 2.0)

    async def testGetMonMatchupAgainstMon(self):
        mon = await PokeapiModel.classes.PokemonSpecies.get(self.conn, 260)
        mon2 = await PokeapiModel.classes.PokemonSpecies.get(self.conn, 254)
        maps = await self.conn.get_mon_matchup_against_mon(mon, mon2)
        self.assertEqual(len(maps), 1)
        self.assertTrue(4.0 in maps)

    async def testHasBranchingEvos(self):
        mon = await PokeapiModel.classes.PokemonSpecies.get(self.conn, 25)
        self.assertFalse(await self.conn.has_branching_evos(mon))
        mon = await PokeapiModel.classes.PokemonSpecies.get(self.conn, 133)
        self.assertTrue(await self.conn.has_branching_evos(mon))

    async def testGetBaseStats(self):
        mon = await PokeapiModel.classes.PokemonSpecies.get(self.conn, 25)
        base_stats = await self.conn.get_base_stats(mon)
        self.assertEqual(len(base_stats), 6)
        self.assertEqual(base_stats['HP'], 35)
        self.assertEqual(base_stats['Attack'], 55)
        self.assertEqual(base_stats['Defense'], 40)
        self.assertEqual(base_stats['Special Attack'], 50)
        self.assertEqual(base_stats['Special Defense'], 50)
        self.assertEqual(base_stats['Speed'], 90)

    async def testGetVersionGroupName(self):
        grp = await PokeapiModel.classes.VersionGroup.get(self.conn, 1)
        self.assertEqual(await self.conn.get_version_group_name(grp), 'Red and Blue')

    async def asyncTearDown(self) -> None:
        await self.conn.close()


if __name__ == '__main__':
    unittest.main()

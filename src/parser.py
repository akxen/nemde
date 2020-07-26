# TODO: create abstract base class


class JSONParser:
    def __init__(self):
        pass

    @staticmethod
    def get_trader_index(data):
        """Get trader index"""

        # Trader period attribute
        elements = (data.get('NEMSPDCaseFile').get('NemSpdInputs').get('PeriodCollection').get('Period')
                    .get('TraderPeriodCollection').get('TraderPeriod'))

        return [i.get('@TraderID') for i in elements]

    @staticmethod
    def get_non_scheduled_generators(data):
        """Get non-scheduled generators"""

        # Non-scheduled generator attribute
        elements = (data.get('NEMSPDCaseFile').get('NemSpdInputs').get('PeriodCollection').get('Period')
                    .get('Non_Scheduled_Generator_Collection').get('Non_Scheduled_Generator'))

        return [i.get('@DUID') for i in elements]

    @staticmethod
    def get_mnsp_index(data):
        """MNSP index"""

        # Get MNSP elements
        elements = (data.get('NEMSPDCaseFile').get('NemSpdInputs').get('PeriodCollection').get('Period')
                    .get('InterconnectorPeriodCollection').get('InterconnectorPeriod'))

        return [i.get('@InterconnectorID') for i in elements if i.get('@MNSP') == '1']

    @staticmethod
    def get_interconnector_index(data):
        """Interconnector index"""

        # Get MNSP elements
        elements = (data.get('NEMSPDCaseFile').get('NemSpdInputs').get('PeriodCollection').get('Period')
                    .get('InterconnectorPeriodCollection').get('InterconnectorPeriod'))

        return [i.get('@InterconnectorID') for i in elements]

    @staticmethod
    def get_trader_offer_index(data):
        """Get trader offer index"""

        # Trader offer index
        elements = (data.get('NEMSPDCaseFile').get('NemSpdInputs').get('PeriodCollection').get('Period')
                    .get('TraderPeriodCollection').get('TraderPeriod'))

        # Container for trader offer index
        trader_offer_index = []

        for trader in elements:
            # Extract offer info
            offer_info = trader.get('TradeCollection').get('Trade')

            # Case when trader has only one offer
            if type(offer_info) == dict:
                trader_offer_index.append((trader.get('@TraderID'), offer_info.get('@TradeType')))

            # Case when trader has multiple offers
            elif type(offer_info) == list:
                for offer in offer_info:
                    trader_offer_index.append((trader.get('@TraderID'), offer.get('@TradeType')))
            else:
                raise Exception(f'Unexpected type: {type(offer_info)}')

        return trader_offer_index

    @staticmethod
    def get_mnsp_offer_index(data):
        """MNSP offer index"""

        # Path to MNSP elements
        path = ".//NemSpdInputs/PeriodCollection/Period/InterconnectorPeriodCollection/InterconnectorPeriod[@MNSP='1']"

        # Get MNSP elements
        mnsps = self.interval_data.findall(path)

        # Construct MNSP offer index based on interconnector ID and region name (price bands for each region)
        mnsp_offer = [(i.get('InterconnectorID'), o.get('RegionID')) for i in mnsps for o in i.findall('.//MNSPOffer')]

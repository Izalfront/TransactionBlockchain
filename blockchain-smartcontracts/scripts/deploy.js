const hre = require('hardhat');

async function main() {
  const BlockchainInterface = await hre.ethers.getContractFactory('BlockchainInterface');
  const blockchainInterface = await BlockchainInterface.deploy();

  await blockchainInterface.deployed();

  console.log('BlockchainInterface deployed to:', blockchainInterface.address);
}

main()
  .then(() => process.exit(0))
  .catch((error) => {
    console.error(error);
    process.exit(1);
  });

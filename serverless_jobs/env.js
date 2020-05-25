'use strict'

const path = require('path')

module.exports.env = () => (
  {
    APP_TOKEN: process.env.APP_TOKEN || '',
    PYTHON_ENV: process.env.PYTHON_ENV || 'development',
  }
)
